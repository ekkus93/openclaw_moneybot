"""Tests for the draft-only email skill."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

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
