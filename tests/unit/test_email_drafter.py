"""Tests for the draft-only email skill."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from openclaw_moneybot.shared import (
    ArchiveConfig,
    Opportunity,
    PolicyDecision,
    TosLegalCheck,
)
from openclaw_moneybot.shared.types import (
    ConfidenceLevel,
    PolicyDecisionType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.email_drafter import EmailDrafter, EmailDraftRequest
from openclaw_moneybot.skills.email_drafter.compliance import evaluate_compliance
from openclaw_moneybot.skills.email_drafter.templates import (
    _disclosure,
    _recipient_line,
    render_template,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_drafter(tmp_path: Path) -> EmailDrafter:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Email test",
            category="bounty",
            status="discovered",
            source_url="https://example.com/opportunity",
            rules_url="https://example.com/rules",
            required_spend_usd=0,
            estimated_revenue_usd=25,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key="opportunity:opp_001",
    )
    ledger_service.record_policy_decision(
        PolicyDecision(
            created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            policy_decision_id="policy_001",
            opportunity_id="opp_001",
            decision=PolicyDecisionType.ALLOW,
            risk_level=RiskLevel.LOW,
            confidence=ConfidenceLevel.HIGH,
            policy_version="v1",
            request_fingerprint="fingerprint",
        ),
        idempotency_key="policy:policy_001",
    )
    ledger_service.record_tos_legal_check(
        TosLegalCheck(
            created_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
            tos_legal_check_id="tos_001",
            opportunity_id="opp_001",
            decision=TosDecisionType.PROCEED,
            confidence=ConfidenceLevel.HIGH,
            platform_terms_summary="Proceed.",
            legal_risk_summary="Low.",
            tos_risk_summary="Low.",
            evidence_archive_ids=["artifact_001"],
        ),
        idempotency_key="tos:tos_001",
    )
    return EmailDrafter(ArchiveConfig(base_directory=tmp_path / "archive"), ledger_service)


def make_request(**overrides: object) -> EmailDraftRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "purpose": "bounty_application",
        "recipient_name": "Maintainer",
        "recipient_email": "maintainer@example.com",
        "recipient_organization": "Example Org",
        "context_summary": "I have a question about the bounty scope.",
        "source_url": "https://example.com/opportunity",
        "policy_decision_id": "policy_001",
        "policy_decision": "allow",
        "tos_legal_check_id": "tos_001",
        "tos_legal_decision": "proceed",
        "allowed_claims": ["I can submit a documentation patch."],
        "forbidden_claims": [],
        "tone": "concise",
        "requested_call_to_action": (
            "Please confirm whether documentation-only submissions are accepted."
        ),
    }
    payload.update(overrides)
    return EmailDraftRequest.model_validate(payload)


def test_bounty_draft_renders(tmp_path: Path) -> None:
    result = make_drafter(tmp_path).draft(make_request())

    assert result.subject
    assert "documentation" in result.body.lower() or "bounty" in result.body.lower()


def test_mass_recipient_input_is_rejected() -> None:
    try:
        make_request(recipient_email="a@example.com,b@example.com")
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected invalid mass-recipient email")


def test_deceptive_identity_claim_is_blocked_for_review(tmp_path: Path) -> None:
    result = make_drafter(tmp_path).draft(
        make_request(
            context_summary="I am a human representative and can guarantee ROI.",
            allowed_claims=["Guaranteed ROI."],
        )
    )

    assert "deceptive_claim_pattern" in result.risk_flags
    assert result.requires_human_review is True


def test_unsupported_earning_claim_is_flagged(tmp_path: Path) -> None:
    result = make_drafter(tmp_path).draft(
        make_request(allowed_claims=["Guaranteed earnings for every submission."])
    )

    assert "unsupported_earnings_claim" in result.risk_flags


def test_missing_policy_decision_blocks_cold_outreach_draft() -> None:
    try:
        make_request(policy_decision_id=None)
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected missing policy decision validation failure")


def test_subject_is_non_empty_and_non_deceptive(tmp_path: Path) -> None:
    result = make_drafter(tmp_path).draft(make_request(purpose="vendor_question"))

    assert result.subject.strip()
    assert "urgent" not in result.subject.lower()


def test_draft_output_is_ledger_ready(tmp_path: Path) -> None:
    result = make_drafter(tmp_path).draft(make_request())

    assert result.ledger_record.email_draft_id == result.email_draft_id
    assert result.evidence_archive_ids


def test_no_send_operation_occurs(tmp_path: Path) -> None:
    result = make_drafter(tmp_path).draft(make_request())

    assert result.mode == "draft_only"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "Maintainer"),
        ({"recipient_name": None}, "Example Org"),
        (
            {"recipient_name": None, "recipient_organization": None},
            "there",
        ),
    ],
)
def test_recipient_line_fallbacks(
    overrides: dict[str, object],
    expected: str,
) -> None:
    assert _recipient_line(make_request(**overrides)) == expected


def test_disclosure_flag_controls_notice() -> None:
    hidden = make_request()
    shown = make_request(automation_disclosure_required=True)

    assert _disclosure(hidden) == ""
    assert "automation assistance" in _disclosure(shown)


def test_render_template_covers_supported_purposes() -> None:
    bounty_template, bounty_subject, bounty_body = render_template(make_request())
    vendor_template, vendor_subject, vendor_body = render_template(
        make_request(
            purpose="vendor_question",
            context_summary="  Need details on the service tier.  ",
            requested_call_to_action="  Share the monthly price.  ",
        )
    )
    receipt_template, receipt_subject, receipt_body = render_template(
        make_request(
            purpose="receipt_request",
            context_summary="  Invoice for the approved purchase.  ",
            requested_call_to_action="  Please resend the invoice PDF.  ",
        )
    )
    followup_template, followup_subject, followup_body = render_template(
        make_request(
            purpose="followup",
            context_summary="  My earlier scoped question.  ",
            requested_call_to_action="  A short confirmation would help.  ",
        )
    )

    assert bounty_template == "bounty_application"
    assert bounty_subject == "Question about the listed bounty"
    assert "https://example.com/opportunity" in bounty_body
    assert "I have a question about the bounty scope." in bounty_body
    assert "Please confirm whether documentation-only submissions are accepted." in bounty_body

    assert vendor_template == "vendor_question"
    assert vendor_subject == "Question about your product or service"
    assert "Need details on the service tier." in vendor_body
    assert "Share the monthly price." in vendor_body

    assert receipt_template == "receipt_request"
    assert receipt_subject == "Receipt request"
    assert "Invoice for the approved purchase." in receipt_body
    assert "Please resend the invoice PDF." in receipt_body

    assert followup_template == "followup"
    assert followup_subject == "Following up on a previous message"
    assert "My earlier scoped question." in followup_body
    assert "A short confirmation would help." in followup_body


def test_render_template_uses_bounty_source_fallback_and_generic_branch() -> None:
    fallback_template, _, fallback_body = render_template(make_request(source_url=None))
    generic_template, generic_subject, generic_body = render_template(
        make_request(
            purpose="status_check",
            context_summary="  Short neutral note.  ",
            requested_call_to_action="  Reply if this is still active.  ",
            automation_disclosure_required=True,
        )
    )

    assert fallback_template == "bounty_application"
    assert "the shared listing" in fallback_body

    assert generic_template == "generic"
    assert generic_subject == "Question"
    assert "Short neutral note." in generic_body
    assert "Reply if this is still active." in generic_body
    assert "automation assistance" in generic_body


def test_compliance_notes_cover_recipient_source_and_purpose_flags() -> None:
    proposal = make_request(
        purpose="proposal",
        recipient_source_url="https://example.com/contact",
        context_summary="Affiliate proposal for one partner.",
    )
    vendor = make_request(purpose="vendor_question")
    bounty = make_request()

    proposal.policy_decision_id = None
    proposal.max_followups = 2

    proposal_flags, proposal_notes, proposal_review = evaluate_compliance(proposal)
    _, vendor_notes, _ = evaluate_compliance(vendor)
    _, bounty_notes, _ = evaluate_compliance(bounty)

    assert {
        "missing_policy_approval",
        "too_many_followups",
    }.issubset(proposal_flags)
    assert proposal_review is True
    assert "recipient_source_url provided for recipient provenance review." in proposal_notes
    assert "compliance_flag:commercial_outreach" in proposal_notes
    assert "compliance_flag:cold_outreach" in proposal_notes
    assert "compliance_flag:affiliate_referral_content" in proposal_notes
    assert "compliance_flag:support_request" in vendor_notes
    assert "compliance_flag:bounty_submission" in bounty_notes


def test_compliance_flags_cover_policy_tos_and_pattern_detection() -> None:
    request = make_request(
        context_summary="We scraped the list and will follow up daily with a fake testimonial.",
        allowed_claims=["We guarantee a payout."],
        forbidden_claims=["Pretend to be the official representative."],
        automation_disclosure_required=True,
    )
    request.recipient_email = "a@example.com,b@example.com"
    request.policy_decision = "block"
    request.tos_legal_decision = "block"

    risk_flags, notes, review_required = evaluate_compliance(request)

    assert review_required is True
    assert {
        "mass_recipient_request",
        "policy_not_allow",
        "tos_not_cleared",
        "deceptive_claim_pattern",
        "scraped_recipient_source",
        "harassment_loop_pattern",
        "unsupported_earnings_claim",
    }.issubset(risk_flags)
    assert "Forbidden claims were supplied and will be omitted from the draft." in notes
    assert "Automation disclosure was included in the draft." in notes


def test_email_draft_request_validates_mode_context_links_and_emails() -> None:
    with pytest.raises(ValidationError):
        make_request(mode="send_now")
    with pytest.raises(ValidationError):
        make_request(context_summary="")
    with pytest.raises(ValidationError):
        make_request(opportunity_id=None, related_experiment_id=None)
    with pytest.raises(ValidationError):
        make_request(purpose="proposal", policy_decision_id=None)
    with pytest.raises(ValidationError):
        make_request(recipient_email="maintainer@invalid")
    with pytest.raises(ValidationError):
        make_request(sender_email="bot@invalid")
