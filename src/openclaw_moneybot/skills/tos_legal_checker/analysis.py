"""Deterministic analysis for terms, rules, and legal risk."""

from __future__ import annotations

from openclaw_moneybot.shared.contracts import TosLegalCheck
from openclaw_moneybot.shared.types import ConfidenceLevel, TosDecisionType
from openclaw_moneybot.skills.moneybot_policy_guard.models import PolicyCheckRequest
from openclaw_moneybot.skills.tos_legal_checker.extract import (
    extract_relevant_snippets,
    normalize_text,
)
from openclaw_moneybot.skills.tos_legal_checker.models import (
    TosLegalCheckRequest,
    TosLegalCheckResult,
)
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now

REJECT_PATTERNS = {
    "automation prohibited": "Terms prohibit automation or bots.",
    "no bots": "Terms prohibit bots.",
    "fake account": "Opportunity requires fake accounts.",
    "mass outreach": "Opportunity requires spam or mass outreach.",
    "handling other people's funds": "Opportunity involves handling funds for others.",
    "gambling": "Opportunity involves gambling or prediction-style activity.",
    "securities": "Opportunity touches regulated finance language.",
    "forex": "Opportunity touches regulated finance language.",
}

REVIEW_PATTERNS = {
    "identity verification": "Identity verification requires review.",
    "recurring billing": "Recurring billing requires review.",
    "collect emails": "User data collection requires review.",
    "affiliate": "Affiliate marketing requires review.",
    "unclear payment": "Payment terms are unclear.",
}


def _classify_policy(
    lowered_text: str,
    *,
    allow_terms: tuple[str, ...] = (),
    prohibit_terms: tuple[str, ...] = (),
    unclear_terms: tuple[str, ...] = (),
) -> str:
    if any(term in lowered_text for term in prohibit_terms):
        return "prohibited"
    if any(term in lowered_text for term in allow_terms):
        return "allowed"
    if any(term in lowered_text for term in unclear_terms):
        return "unclear"
    return "unknown"


def analyze_tos_legal_request(request: TosLegalCheckRequest) -> TosLegalCheckResult:
    """Return a deterministic TOS/legal assessment."""
    normalized_text = normalize_text(request.evidence_text or "")
    snippets = extract_relevant_snippets(request.evidence_text or "")
    red_flags: list[str] = []
    mitigations: list[str] = []
    required_records = ["terms_snapshot"]
    decision = TosDecisionType.PROCEED
    confidence = ConfidenceLevel.HIGH
    legal_summary = "No obvious regulated or deceptive activity detected."
    tos_summary = "No explicit terms conflict detected."

    if request.rules_url is None and not request.evidence_archive_ids and not normalized_text:
        decision = TosDecisionType.HUMAN_REVIEW
        confidence = ConfidenceLevel.MEDIUM
        legal_summary = "Rules source is missing."
        tos_summary = "Cannot verify platform rules."
        mitigations.append("Archive the rules or terms page before proceeding.")

    if not normalized_text and request.rules_url is None:
        decision = TosDecisionType.HUMAN_REVIEW
        confidence = ConfidenceLevel.MEDIUM
        legal_summary = "No readable rules were provided."
        tos_summary = "Rules are unavailable."
        mitigations.append("Collect readable rules or terms evidence.")

    lowered_text = normalized_text.lower()
    automation_policy = _classify_policy(
        lowered_text,
        allow_terms=("automation allowed", "bots allowed", "automation permitted"),
        prohibit_terms=("automation prohibited", "no bots", "bot use prohibited"),
        unclear_terms=("automation unclear",),
    )
    bot_account_policy = _classify_policy(
        lowered_text,
        allow_terms=("bot accounts allowed",),
        prohibit_terms=("fake account", "no fake accounts", "account sharing prohibited"),
    )
    payment_policy = _classify_policy(
        lowered_text,
        allow_terms=("payment after acceptance", "paid after approval", "payout within"),
        unclear_terms=("payment unclear", "payment terms unavailable", "unclear payment"),
    )
    eligibility_policy = _classify_policy(
        lowered_text,
        allow_terms=("open to individual developers", "eligible participants"),
        unclear_terms=("eligibility unclear", "eligibility may change"),
    )
    identity_policy = _classify_policy(
        lowered_text,
        prohibit_terms=("kyc required",),
        unclear_terms=("identity verification", "government id"),
    )
    recurring_billing_policy = _classify_policy(
        lowered_text,
        prohibit_terms=("automatic renewal",),
        unclear_terms=("recurring billing", "subscription renews"),
    )
    refund_policy = _classify_policy(
        lowered_text,
        allow_terms=("refundable", "refund available"),
        unclear_terms=("chargeback", "refund policy unclear"),
    )
    outreach_policy = _classify_policy(
        lowered_text,
        prohibit_terms=("scraping prohibited", "no mass outreach", "no cold outreach"),
        unclear_terms=("contact restrictions", "outreach may be limited"),
    )
    third_party_funds_policy = _classify_policy(
        lowered_text,
        prohibit_terms=("handling other people's funds", "hold funds on behalf"),
    )

    for pattern, reason in REJECT_PATTERNS.items():
        if pattern in lowered_text:
            decision = TosDecisionType.REJECT
            confidence = ConfidenceLevel.HIGH
            red_flags.append(reason)

    if decision is not TosDecisionType.REJECT:
        for pattern, reason in REVIEW_PATTERNS.items():
            if pattern in lowered_text:
                decision = TosDecisionType.HUMAN_REVIEW
                confidence = ConfidenceLevel.MEDIUM
                mitigations.append(reason)

    if "commercial use prohibited" in lowered_text:
        decision = TosDecisionType.REJECT
        confidence = ConfidenceLevel.HIGH
        red_flags.append("Terms prohibit the commercial use required by the action.")

    if "payment terms unavailable" in lowered_text or "payment unclear" in lowered_text:
        decision = TosDecisionType.HUMAN_REVIEW
        confidence = ConfidenceLevel.MEDIUM
        mitigations.append("Clarify payout and payment rules before execution.")
    if any(
        policy == "prohibited"
        for policy in (
            automation_policy,
            bot_account_policy,
            third_party_funds_policy,
        )
    ):
        decision = TosDecisionType.REJECT
        confidence = ConfidenceLevel.HIGH
    elif any(
        policy == "unclear"
        for policy in (
            payment_policy,
            eligibility_policy,
            identity_policy,
            recurring_billing_policy,
            refund_policy,
            outreach_policy,
        )
    ) and decision is not TosDecisionType.REJECT:
        decision = TosDecisionType.HUMAN_REVIEW
        confidence = ConfidenceLevel.MEDIUM

    labeled_snippets = list(snippets)
    for label, policy in {
        "automation": automation_policy,
        "bot_accounts": bot_account_policy,
        "payment": payment_policy,
        "eligibility": eligibility_policy,
        "identity": identity_policy,
        "recurring_billing": recurring_billing_policy,
        "refund": refund_policy,
        "outreach": outreach_policy,
        "third_party_funds": third_party_funds_policy,
    }.items():
        if policy != "unknown":
            labeled_snippets.append(f"[{label}] {policy}")

    if red_flags:
        legal_summary = "; ".join(red_flags)
        tos_summary = "Terms or rules contain disqualifying restrictions."
    elif mitigations:
        legal_summary = "The opportunity may be legal, but important questions remain."
        tos_summary = "Terms require clarification or mitigation before execution."
    else:
        required_records.append("submission_receipt")

    ledger_record = TosLegalCheck(
        created_at=utc_now(),
        tos_legal_check_id=make_id("tos"),
        opportunity_id=request.opportunity_id,
        source_url=request.source_url,
        decision=decision,
        confidence=confidence,
        platform_terms_summary=tos_summary,
        legal_risk_summary=legal_summary,
        tos_risk_summary=tos_summary,
        red_flags=red_flags,
        required_mitigations=mitigations,
        required_records=required_records,
        source_quotes_or_snippets=labeled_snippets,
        evidence_archive_ids=request.evidence_archive_ids,
        automation_policy=automation_policy,
        bot_account_policy=bot_account_policy,
        payment_policy=payment_policy,
        eligibility_policy=eligibility_policy,
        identity_policy=identity_policy,
        recurring_billing_policy=recurring_billing_policy,
        refund_policy=refund_policy,
        outreach_policy=outreach_policy,
        third_party_funds_policy=third_party_funds_policy,
    )
    handoff = PolicyCheckRequest(
        action_id=make_id("policy_request"),
        action_type="research",
        title=f"TOS/legal review for {request.opportunity_name}",
        description=request.proposed_action,
        category="research",
        counterparty=request.counterparty,
        amount_usd=request.spend_amount_usd,
        source_urls=[request.source_url],
        planned_tools=[],
        metadata={
            "opportunity_id": request.opportunity_id,
            "tos_legal_check_id": ledger_record.tos_legal_check_id,
            "red_flags": red_flags,
        },
    ).model_dump(mode="json")
    return TosLegalCheckResult(
        decision=decision.value,
        confidence=confidence.value,
        platform_terms_summary=tos_summary,
        legal_risk_summary=legal_summary,
        tos_risk_summary=tos_summary,
        red_flags=red_flags,
        required_mitigations=mitigations,
        required_records=required_records,
        source_quotes_or_snippets=labeled_snippets,
        evidence_archive_ids=request.evidence_archive_ids,
        checker_version="v1",
        handoff_to_policy_guard=handoff,
        ledger_record=ledger_record,
    )
