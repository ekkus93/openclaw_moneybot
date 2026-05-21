"""Tests for the browser governor service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.plugins.browser_governor import (
    BrowserActionCompletionRequest,
    BrowserActionRequest,
    BrowserAutomationBackend,
    BrowserAutomationError,
    BrowserExecutionArtifacts,
    BrowserExecutionRequest,
    BrowserGovernorService,
    BrowserPageSnapshot,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    BrowserGovernorConfig,
    LedgerRecord,
    Opportunity,
    PolicyDecision,
)
from openclaw_moneybot.shared.types import (
    ActionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RecordType,
    RiskLevel,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.utils.time import utc_now


def make_service(
    tmp_path: Path,
    *,
    enabled: bool,
    allow_policy: bool = True,
    execution_enabled: bool = False,
    allowed_hosts: list[str] | None = None,
    automation_backend: BrowserAutomationBackend | None = None,
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
        BrowserGovernorConfig(
            enabled=enabled,
            allowed_profile_ids=["moneybot-default"],
            execution_enabled=execution_enabled,
            allowed_hosts=[] if allowed_hosts is None else allowed_hosts,
        ),
        ledger_service,
        archiver,
        automation_backend=automation_backend,
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


def make_execution_request(**overrides: object) -> BrowserExecutionRequest:
    payload: dict[str, object] = {
        "action_id": "browser-exec-1",
        "opportunity_id": "opp_browser",
        "policy_decision_id": "policy_browser",
        "action_type": ActionType.BROWSER_SUBMIT,
        "profile_id": "moneybot-default",
        "target_url": "https://example.com/form",
        "purpose": "Submit one approved form.",
        "steps": [
            {"kind": "fill", "selector": "#email", "text": "bot@example.com"},
            {"kind": "click", "selector": "#submit"},
            {"kind": "wait_for_text", "text": "Submitted"},
        ],
    }
    payload.update(overrides)
    return BrowserExecutionRequest.model_validate(payload)


class FakeAutomationBackend:
    def __init__(self) -> None:
        self.calls = 0

    def execute(
        self,
        config: BrowserGovernorConfig,
        request: BrowserExecutionRequest,
    ) -> BrowserExecutionArtifacts:
        self.calls += 1
        assert config.browser_engine == "firefox"
        assert request.profile_id == "moneybot-default"
        return BrowserExecutionArtifacts(
            before=BrowserPageSnapshot(
                url=str(request.target_url),
                page_text="Visible form before submit.",
                html="<html><body>Visible form before submit.</body></html>",
                page_title="Before",
            ),
            after=BrowserPageSnapshot(
                url="https://example.com/confirmation",
                page_text="Submitted successfully.",
                html="<html><body>Submitted successfully.</body></html>",
                page_title="After",
            ),
            result_summary="Executed 3 bounded browser step(s) with Playwright Firefox.",
            applied_step_count=3,
        )


class FailingAutomationBackend:
    def execute(
        self,
        config: BrowserGovernorConfig,
        request: BrowserExecutionRequest,
    ) -> BrowserExecutionArtifacts:
        raise BrowserAutomationError(f"boom for {request.action_id}")


def test_prepare_rejects_when_browser_governor_disabled(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=False)

    result = service.prepare_action(make_prepare_request())

    assert result.status == "rejected"
    assert result.reason == "browser_disabled"


def test_execute_action_runs_bounded_backend_and_archives_linked_evidence(tmp_path: Path) -> None:
    backend = FakeAutomationBackend()
    service = make_service(
        tmp_path,
        enabled=True,
        execution_enabled=True,
        allowed_hosts=["example.com"],
        automation_backend=backend,
    )

    result = service.execute_action(make_execution_request())
    evidence = service.ledger_service.list_evidence_for_related(
        related_type=RecordType.OPPORTUNITY,
        related_id="opp_browser",
    )

    assert result.status == "completed"
    assert result.before_evidence_id is not None
    assert result.after_evidence_id is not None
    assert result.final_url == "https://example.com/confirmation"
    assert result.result_summary == "Executed 3 bounded browser step(s) with Playwright Firefox."
    assert backend.calls == 1
    assert {
        record.evidence_type
        for record in evidence
        if record.evidence_type.startswith("browser_")
    } >= {
        "browser_before_action",
        "browser_before_html_snapshot",
        "browser_after_action",
        "browser_after_html_snapshot",
    }


def test_execute_action_reuses_prior_automation_result_for_matching_replay(tmp_path: Path) -> None:
    backend = FakeAutomationBackend()
    service = make_service(
        tmp_path,
        enabled=True,
        execution_enabled=True,
        allowed_hosts=["example.com"],
        automation_backend=backend,
    )

    first = service.execute_action(make_execution_request(action_id="browser-exec-replay"))
    second = service.execute_action(make_execution_request(action_id="browser-exec-replay"))

    assert first.audit_record_id == second.audit_record_id
    assert first.before_evidence_id == second.before_evidence_id
    assert first.after_evidence_id == second.after_evidence_id
    assert backend.calls == 1


def test_execute_action_rejects_when_live_execution_is_disabled(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=True)

    result = service.execute_action(make_execution_request())

    assert result.status == "rejected"
    assert result.reason == "browser_execution_disabled"


def test_execute_action_rejects_non_allowlisted_target_host(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        enabled=True,
        execution_enabled=True,
        allowed_hosts=["example.net"],
        automation_backend=FakeAutomationBackend(),
    )

    result = service.execute_action(make_execution_request())

    assert result.status == "rejected"
    assert result.reason == "target_host_not_allowlisted"


def test_execute_action_records_backend_failures_as_rejections(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        enabled=True,
        execution_enabled=True,
        allowed_hosts=["example.com"],
        automation_backend=FailingAutomationBackend(),
    )

    result = service.execute_action(make_execution_request(action_id="browser-exec-fail"))

    assert result.status == "rejected"
    assert result.reason == "browser_execution_failed"


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


def test_prepare_rejects_non_allowlisted_profile_and_extra_flags(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=True)

    wrong_profile = service.prepare_action(
        make_prepare_request(profile_id="other-profile")
    )
    evasion = service.prepare_action(
        make_prepare_request(action_id="browser-action-5", uses_bot_evasion=True)
    )
    mass_signup = service.prepare_action(
        make_prepare_request(action_id="browser-action-6", mass_signup=True)
    )
    scraping = service.prepare_action(
        make_prepare_request(action_id="browser-action-7", scraping_against_terms=True)
    )

    assert wrong_profile.reason == "profile_not_allowlisted"
    assert evasion.reason == "bot_evasion_blocked"
    assert mass_signup.reason == "mass_signup_blocked"
    assert scraping.reason == "scraping_against_terms_blocked"


def test_prepare_purchase_with_unknown_spend_request_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=True)

    result = service.prepare_action(
        make_prepare_request(
            action_id="browser-action-8",
            action_type=ActionType.PURCHASE,
            spend_request_id="spend_missing",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "spend_request_missing"


def test_prepare_rejects_missing_opportunity_and_policy_states(tmp_path: Path) -> None:
    missing_opp_path = tmp_path / "missing-opp"
    missing_opp_path.mkdir()
    missing_opportunity_service = make_service(missing_opp_path, enabled=True)
    missing_opportunity = missing_opportunity_service.prepare_action(
        make_prepare_request(opportunity_id="opp_missing")
    )

    missing_policy_path = tmp_path / "missing-policy"
    missing_policy_path.mkdir()
    missing_policy_service = make_service(missing_policy_path, enabled=True)
    missing_policy = missing_policy_service.prepare_action(
        make_prepare_request(policy_decision_id="policy_missing")
    )

    blocked_policy_path = tmp_path / "blocked-policy"
    blocked_policy_path.mkdir()
    blocked_policy_service = make_service(
        blocked_policy_path,
        enabled=True,
        allow_policy=False,
    )
    blocked_policy = blocked_policy_service.prepare_action(make_prepare_request())

    assert missing_opportunity.reason == "opportunity_missing"
    assert missing_policy.reason == "policy_missing"
    assert blocked_policy.reason == "policy_not_allow"


def test_complete_rejects_when_browser_governor_disabled(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=False)

    result = service.complete_action(
        BrowserActionCompletionRequest(
            action_id="browser-action-disabled",
            opportunity_id="opp_browser",
            after_page_text="After page",
            result_summary="Blocked by config.",
            success=False,
        )
    )

    assert result.status == "rejected"
    assert result.reason == "browser_disabled"


def test_prepare_payload_lookup_ignores_unrelated_audit_events(tmp_path: Path) -> None:
    service = make_service(tmp_path, enabled=True)
    prepared = service.prepare_action(make_prepare_request())
    service.ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=utc_now(),
            record_id="audit_unrelated",
            record_type=RecordType.AUDIT_EVENT,
            related_record_id="other-action",
            payload={
                "kind": "browser_action_prepare",
                "status": "approved",
                "action_id": "other-action",
                "before_evidence_id": "artifact_other",
            },
        ),
        idempotency_key="audit:browser:unrelated",
    )

    completed = service.complete_action(
        BrowserActionCompletionRequest(
            action_id="browser-action-1",
            opportunity_id="opp_browser",
            after_page_text="Confirmation page text after submit.",
            result_summary="Submitted successfully.",
            success=True,
        )
    )

    assert completed.status == "completed"
    assert completed.before_evidence_id == prepared.before_evidence_id
