"""Compliance checks for draft-only emails."""

from __future__ import annotations

from openclaw_moneybot.skills.email_drafter.models import EmailDraftRequest

DECEPTIVE_PATTERNS = (
    "guaranteed roi",
    "guaranteed return",
    "fake testimonial",
    "limited time only",
    "urgent act now",
    "i am a human",
    "official representative",
    "act immediately",
)


def evaluate_compliance(request: EmailDraftRequest) -> tuple[list[str], list[str], bool]:
    """Return risk flags, compliance notes, and whether human review is needed."""
    risk_flags: list[str] = []
    notes: list[str] = []
    review_required = False

    purpose = request.purpose.lower()
    if "," in request.recipient_email:
        risk_flags.append("mass_recipient_request")
    if request.recipient_source_url is not None:
        notes.append("recipient_source_url provided for recipient provenance review.")
    outbound_purposes = {"proposal", "bounty_application", "vendor_question"}
    if request.policy_decision_id is None and purpose in outbound_purposes:
        risk_flags.append("missing_policy_approval")
        review_required = True
    if request.policy_decision not in {None, "allow"} and purpose in outbound_purposes:
        risk_flags.append("policy_not_allow")
        review_required = True
    if request.tos_legal_decision not in {None, "proceed"}:
        risk_flags.append("tos_not_cleared")
        review_required = True
    if request.max_followups > 1:
        risk_flags.append("too_many_followups")
        review_required = True
    if purpose in {"proposal", "bounty_application"}:
        notes.append("compliance_flag:commercial_outreach")
    if purpose == "proposal":
        notes.append("compliance_flag:cold_outreach")
    if "affiliate" in request.context_summary.lower():
        notes.append("compliance_flag:affiliate_referral_content")
    if purpose == "bounty_application":
        notes.append("compliance_flag:bounty_submission")
    if purpose == "vendor_question":
        notes.append("compliance_flag:support_request")
    lowered_context = f"{request.context_summary} {' '.join(request.allowed_claims)}".lower()
    for pattern in DECEPTIVE_PATTERNS:
        if pattern in lowered_context:
            risk_flags.append("deceptive_claim_pattern")
            review_required = True
            break
    if "scraped" in lowered_context:
        risk_flags.append("scraped_recipient_source")
        review_required = True
    if "follow up daily" in lowered_context or "keep messaging" in lowered_context:
        risk_flags.append("harassment_loop_pattern")
        review_required = True
    if any("guarantee" in claim.lower() for claim in request.allowed_claims):
        risk_flags.append("unsupported_earnings_claim")
        review_required = True
    if request.forbidden_claims:
        notes.append("Forbidden claims were supplied and will be omitted from the draft.")
    if request.automation_disclosure_required:
        notes.append("Automation disclosure was included in the draft.")
    return risk_flags, notes, review_required
