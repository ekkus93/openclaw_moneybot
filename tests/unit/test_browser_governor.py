"""Tests for the browser governor service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.plugins.browser_governor import (
    BrowserActionCompletionRequest,
    BrowserActionRequest,
    BrowserGovernorService,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    BrowserGovernorConfig,
    Opportunity,
    PolicyDecision,
)
from openclaw_moneybot.shared.types import (
    ActionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RiskLevel,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver


def make_service(
    tmp_path: Path,
    *,
    enabled: bool,
    allow_policy: bool = True,
) -> BrowserGovernorService:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_browser",
            name="Browser opportunity",
            category="bounty",
            status="approved",
            source_url="https://example.com/form",
            required_spend_usd=0,
            estimated_revenue_usd=20,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key="opportunity:opp_browser",
    )
    ledger_service.record_policy_decision(
        PolicyDecision(
            created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            policy_decision_id="policy_browser",
            opportunity_id="opp_browser",
            decision=PolicyDecisionType.ALLOW if allow_policy else PolicyDecisionType.NEEDS_REVIEW,
            risk_level=RiskLevel.LOW,
            confidence=ConfidenceLevel.HIGH,
            policy_version="v1",
            request_fingerprint="fingerprint",
        ),
        idempotency_key="policy:policy_browser",
    )
    archiver = ReceiptAndEvidenceArchiver(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )
    return BrowserGovernorService(
        BrowserGovernorConfig(enabled=enabled, allowed_profile_ids=["moneybot-default"]),
        ledger_service,
        archiver,
    )


def make_prepare_request(**overrides: object) -> BrowserActionRequest:
    payload: dict[str, object] = {
        "action_id": "browser-action-1",
        "opportunity_id": "opp_browser",
        "policy_decision_id": "policy_browser",
        "action_type": ActionType.BROWSER_SUBMIT,
        "profile_id": "moneybot-default",
        "target_url": "https://example.com/form",
        "purpose": "Submit one approved form.",
        "before_page_text": "Visible form fields before submit.",
    }
    payload.update(overrides)
    return BrowserActionRequest.model_validate(payload)


def test_prepare_rejects_when_browser_governor_disabled(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=False)

    result = service.prepare_action(make_prepare_request())

    assert result.status == "rejected"
    assert result.reason == "browser_disabled"


def test_prepare_rejects_unsafe_browser_flags(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=True)

    personal = service.prepare_action(make_prepare_request(uses_personal_account=True))
    kyc = service.prepare_action(
        make_prepare_request(action_id="browser-action-2", requires_kyc=True)
    )
    captcha = service.prepare_action(
        make_prepare_request(action_id="browser-action-3", attempts_captcha_bypass=True)
    )

    assert personal.reason == "personal_account_blocked"
    assert kyc.reason == "kyc_requires_human_review"
    assert captcha.reason == "captcha_bypass_blocked"


def test_prepare_requires_wallet_reference_for_purchase(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=True)

    result = service.prepare_action(
        make_prepare_request(action_id="browser-action-4", action_type=ActionType.PURCHASE)
    )

    assert result.status == "rejected"
    assert result.reason == "wallet_spend_required"


def test_prepare_and_complete_archive_before_and_after_evidence(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=True)

    prepared = service.prepare_action(make_prepare_request())
    completed = service.complete_action(
        BrowserActionCompletionRequest(
            action_id="browser-action-1",
            opportunity_id="opp_browser",
            after_page_text="Confirmation page text after submit.",
            result_summary="Submitted successfully.",
            success=True,
        )
    )

    assert prepared.status == "approved"
    assert prepared.before_evidence_id is not None
    assert completed.status == "completed"
    assert completed.before_evidence_id == prepared.before_evidence_id
    assert completed.after_evidence_id is not None


def test_complete_requires_prior_prepare(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=True)

    result = service.complete_action(
        BrowserActionCompletionRequest(
            action_id="missing-action",
            opportunity_id="opp_browser",
            after_page_text="Confirmation page text after submit.",
            result_summary="Submitted successfully.",
            success=True,
        )
    )

    assert result.status == "rejected"
    assert result.reason == "prepare_missing"
