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
        decision=decision,
        confidence=confidence,
        platform_terms_summary=tos_summary,
        legal_risk_summary=legal_summary,
        tos_risk_summary=tos_summary,
        red_flags=red_flags,
        required_mitigations=mitigations,
        required_records=required_records,
        source_quotes_or_snippets=snippets,
        evidence_archive_ids=request.evidence_archive_ids,
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
        source_quotes_or_snippets=snippets,
        evidence_archive_ids=request.evidence_archive_ids,
        checker_version="v1",
        handoff_to_policy_guard=handoff,
        ledger_record=ledger_record,
    )
