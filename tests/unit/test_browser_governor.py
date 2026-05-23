"""Tests for the browser governor service."""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

import openclaw_moneybot.plugins.browser_governor.backend as browser_backend
from openclaw_moneybot.plugins.browser_governor import (
    BrowserActionCompletionRequest,
    BrowserActionRequest,
    BrowserAutomationBackend,
    BrowserAutomationError,
    BrowserExecutionArtifacts,
    BrowserExecutionRequest,
    BrowserExecutionStep,
    BrowserGovernorService,
    BrowserPageSnapshot,
    PlaywrightFirefoxBackend,
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


class FakeLocator:
    def __init__(self, text_values: list[str | None] | None = None) -> None:
        self.filled: list[tuple[str, int]] = []
        self.click_timeouts: list[int] = []
        self.text_values = [""] if text_values is None else text_values

    def fill(self, value: str, *, timeout: int) -> None:
        self.filled.append((value, timeout))

    def click(self, *, timeout: int) -> None:
        self.click_timeouts.append(timeout)

    def text_content(self, *, timeout: int) -> str | None:
        assert timeout >= 0
        if len(self.text_values) == 1:
            return self.text_values[0]
        return self.text_values.pop(0)


class FakePage:
    def __init__(
        self,
        *,
        url: str = "https://example.com/form",
        body_values: list[str | None] | None = None,
        html: str = "<html><body>Visible form</body></html>",
        title: str = "Example",
        screenshot: bytes = b"png",
        locator_map: dict[str, FakeLocator] | None = None,
    ) -> None:
        self.url = url
        self._body_values = ["Visible form"] if body_values is None else body_values
        self._html = html
        self._title = title
        self._screenshot = screenshot
        self.goto_calls: list[tuple[str, str, int]] = []
        self.locator_map = {} if locator_map is None else locator_map

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append((url, wait_until, timeout))
        self.url = url

    def locator(self, selector: str) -> FakeLocator:
        return self.locator_map.setdefault(selector, FakeLocator())

    def content(self) -> str:
        return self._html

    def title(self) -> str:
        return self._title

    def screenshot(self, *, type: str, full_page: bool, timeout: int) -> bytes:
        assert type == "png"
        assert full_page is True
        assert timeout >= 0
        return self._screenshot

    def text_content(self, selector: str) -> str | None:
        assert selector == "body"
        if len(self._body_values) == 1:
            return self._body_values[0]
        return self._body_values.pop(0)


class FakeBrowserContext:
    def __init__(
        self,
        *,
        pages: list[FakePage] | None = None,
        new_page: FakePage | None = None,
    ) -> None:
        self.pages = [] if pages is None else pages
        self._new_page = FakePage() if new_page is None else new_page
        self.default_timeout_ms: int | None = None
        self.closed = False
        self.new_page_calls = 0

    def set_default_timeout(self, timeout_ms: int) -> None:
        self.default_timeout_ms = timeout_ms

    def new_page(self) -> FakePage:
        self.new_page_calls += 1
        return self._new_page

    def close(self) -> None:
        self.closed = True


def install_fake_playwright(
    monkeypatch: pytest.MonkeyPatch,
    *,
    context: FakeBrowserContext | None = None,
    launch_error_message: str | None = None,
) -> FakeBrowserContext | None:
    fake_context = context

    class FakePlaywrightError(Exception):
        pass

    def launch_persistent_context(*, user_data_dir: str, headless: bool) -> FakeBrowserContext:
        assert user_data_dir
        assert isinstance(headless, bool)
        if launch_error_message is not None:
            raise FakePlaywrightError(launch_error_message)
        assert fake_context is not None
        return fake_context

    class SyncPlaywrightManager:
        def __enter__(self) -> types.SimpleNamespace:
            firefox = types.SimpleNamespace(
                launch_persistent_context=launch_persistent_context,
            )
            return types.SimpleNamespace(firefox=firefox)

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    sync_api = cast(Any, types.ModuleType("playwright.sync_api"))
    sync_api.Error = FakePlaywrightError
    sync_api.sync_playwright = lambda: SyncPlaywrightManager()
    playwright = cast(Any, types.ModuleType("playwright"))
    playwright.sync_api = sync_api
    monkeypatch.setitem(sys.modules, "playwright", playwright)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    return fake_context


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


def test_resolve_profile_dir_and_allowed_host_helpers(tmp_path: Path) -> None:
    profile_dir = browser_backend._resolve_profile_dir(
        tmp_path,
        "MoneyBot Default../unsafe__profile!!",
    )

    assert profile_dir == (tmp_path / "moneybotdefaultunsafe__profile").resolve()
    assert profile_dir.is_relative_to(tmp_path.resolve())

    with pytest.raises(BrowserAutomationError, match="safe character"):
        browser_backend._resolve_profile_dir(tmp_path, "!!!")

    browser_backend._assert_allowed_host("https://Example.com/form", ["example.com"])

    with pytest.raises(BrowserAutomationError, match="not allowlisted"):
        browser_backend._assert_allowed_host("https://other.example/form", ["example.com"])

    with pytest.raises(BrowserAutomationError, match="not allowlisted"):
        browser_backend._assert_allowed_host("file:///tmp/page.html", ["example.com"])


def test_page_snapshot_and_require_string_helpers(tmp_path: Path) -> None:
    config = BrowserGovernorConfig(
        enabled=True,
        allowed_profile_ids=["moneybot-default"],
    )
    page = FakePage(
        body_values=["  text on page  "],
        html="<html><body>text on page</body></html>",
        title="Browser page",
        screenshot=b"image-bytes",
    )

    assert browser_backend._read_page_text(page) == "text on page"
    page_with_empty_body = FakePage(body_values=[None])
    assert browser_backend._read_page_text(page_with_empty_body) == ""

    snapshot = browser_backend._capture_page(page, config)

    assert snapshot.url == "https://example.com/form"
    assert snapshot.page_text == "text on page"
    assert snapshot.html == "<html><body>text on page</body></html>"
    assert snapshot.page_title == "Browser page"
    assert snapshot.screenshot_png == b"image-bytes"
    assert browser_backend._require_string("value") == "value"
    with pytest.raises(BrowserAutomationError, match="unexpectedly missing"):
        browser_backend._require_string(None)


def test_apply_step_branches_and_missing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    fill_locator = FakeLocator()
    click_locator = FakeLocator()
    page = FakePage(locator_map={"#email": fill_locator, "#submit": click_locator})

    browser_backend._apply_step(
        page,
        BrowserExecutionStep(kind="fill", selector="#email", text="bot@example.com"),
    )
    browser_backend._apply_step(
        page,
        BrowserExecutionStep(kind="click", selector="#submit"),
    )

    wait_call: dict[str, object] = {}

    def fake_wait_for_text(
        current_page: FakePage,
        *,
        expected: str,
        selector: str | None,
        timeout_ms: int,
    ) -> None:
        wait_call.update(
            {
                "page": current_page,
                "expected": expected,
                "selector": selector,
                "timeout_ms": timeout_ms,
            }
        )

    monkeypatch.setattr(browser_backend, "_wait_for_text", fake_wait_for_text)
    browser_backend._apply_step(
        page,
        BrowserExecutionStep(kind="wait_for_text", text="Submitted"),
    )

    assert fill_locator.filled == [("bot@example.com", 5000)]
    assert click_locator.click_timeouts == [5000]
    assert wait_call == {
        "page": page,
        "expected": "Submitted",
        "selector": None,
        "timeout_ms": 5000,
    }

    with pytest.raises(BrowserAutomationError, match="unexpectedly missing"):
        browser_backend._apply_step(
            page,
            BrowserExecutionStep.model_construct(
                kind="fill",
                selector=None,
                text="bot@example.com",
                timeout_ms=1000,
            ),
        )
    with pytest.raises(BrowserAutomationError, match="unexpectedly missing"):
        browser_backend._apply_step(
            page,
            BrowserExecutionStep.model_construct(
                kind="fill",
                selector="#email",
                text=None,
                timeout_ms=1000,
            ),
        )
    with pytest.raises(BrowserAutomationError, match="unexpectedly missing"):
        browser_backend._apply_step(
            page,
            BrowserExecutionStep.model_construct(
                kind="wait_for_text",
                selector=None,
                text=None,
                timeout_ms=1000,
            ),
        )


def test_wait_for_text_succeeds_and_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    success_timeline = iter([0.0, 0.0, 0.01, 0.03])
    monkeypatch.setattr(
        "openclaw_moneybot.plugins.browser_governor.backend.time.monotonic",
        lambda: next(success_timeline),
    )
    monkeypatch.setattr(
        "openclaw_moneybot.plugins.browser_governor.backend.time.sleep",
        lambda seconds: None,
    )
    page = FakePage(body_values=["still waiting", "now Submitted"])
    browser_backend._wait_for_text(page, expected="Submitted", selector=None, timeout_ms=50)

    selector_timeline = iter([0.0, 0.0, 0.01, 0.03])
    monkeypatch.setattr(
        "openclaw_moneybot.plugins.browser_governor.backend.time.monotonic",
        lambda: next(selector_timeline),
    )
    selector_page = FakePage(locator_map={"#status": FakeLocator([None, "done Submitted"])})
    browser_backend._wait_for_text(
        selector_page,
        expected="Submitted",
        selector="#status",
        timeout_ms=50,
    )

    timeline = iter([0.0, 0.0, 0.06])
    monkeypatch.setattr(
        "openclaw_moneybot.plugins.browser_governor.backend.time.monotonic",
        lambda: next(timeline),
    )
    timeout_page = FakePage(body_values=["never"])

    with pytest.raises(BrowserAutomationError, match="Timed out waiting for text"):
        browser_backend._wait_for_text(
            timeout_page,
            expected="Submitted",
            selector=None,
            timeout_ms=50,
        )


def test_browser_execution_step_validators_reject_invalid_combinations() -> None:
    step = BrowserExecutionStep(kind=" FILL ", selector=" #email ", text="bot@example.com")

    assert step.kind == "fill"
    assert step.selector == "#email"

    with pytest.raises(ValueError, match="fill steps require a selector"):
        BrowserExecutionStep(kind="fill", selector=" ", text="x")
    with pytest.raises(ValueError, match="fill steps require text"):
        BrowserExecutionStep(kind="fill", selector="#email", text=None)
    with pytest.raises(ValueError, match="click steps do not accept text"):
        BrowserExecutionStep(kind="click", selector="#go", text="x")
    with pytest.raises(ValueError, match="wait_for_text steps require text"):
        BrowserExecutionStep(kind="wait_for_text", text=None)
    with pytest.raises(ValueError, match="kind must be one of"):
        BrowserExecutionStep(kind="hover")


def test_playwright_firefox_backend_execute_success_and_truncates_steps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = FakePage(body_values=["Submitted", "Submitted"])
    context = FakeBrowserContext(pages=[page])
    install_fake_playwright(monkeypatch, context=context)
    backend = PlaywrightFirefoxBackend()
    config = BrowserGovernorConfig(
        enabled=True,
        execution_enabled=True,
        allowed_profile_ids=["moneybot-default"],
        allowed_hosts=["example.com"],
        profile_root=tmp_path / "profiles",
        max_steps=2,
        default_timeout_ms=1500,
        navigation_timeout_ms=2500,
    )
    request = make_execution_request(
        steps=[
            {"kind": "fill", "selector": "#email", "text": "bot@example.com"},
            {"kind": "click", "selector": "#submit"},
            {"kind": "wait_for_text", "text": "Submitted"},
        ],
    )

    result = backend.execute(config, request)

    assert result.applied_step_count == 2
    assert result.result_summary == "Executed 2 bounded browser step(s) with Playwright Firefox."
    assert context.default_timeout_ms == 1500
    assert context.closed is True
    assert context.new_page_calls == 0
    assert page.goto_calls == [
        ("https://example.com/form", "domcontentloaded", 2500),
    ]
    assert page.locator("#email").filled == [("bot@example.com", 5000)]
    assert page.locator("#submit").click_timeouts == [5000]
    assert (tmp_path / "profiles" / "moneybot-default").is_dir()


def test_playwright_firefox_backend_execute_uses_new_page_and_closes_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    new_page = FakePage()
    context = FakeBrowserContext(pages=[], new_page=new_page)
    install_fake_playwright(monkeypatch, context=context)
    backend = PlaywrightFirefoxBackend()
    config = BrowserGovernorConfig(
        enabled=True,
        execution_enabled=True,
        allowed_profile_ids=["moneybot-default"],
        allowed_hosts=["example.com"],
        profile_root=tmp_path / "profiles",
    )
    bad_request = make_execution_request().model_copy(
        update={
            "steps": [
                BrowserExecutionStep.model_construct(
                    kind="click",
                    selector=None,
                    text=None,
                    timeout_ms=1000,
                )
            ]
        }
    )

    with pytest.raises(BrowserAutomationError, match="unexpectedly missing"):
        backend.execute(config, bad_request)

    assert context.new_page_calls == 1
    assert context.closed is True


def test_playwright_firefox_backend_execute_wraps_playwright_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_playwright(
        monkeypatch,
        launch_error_message="launch failed",
    )
    backend = PlaywrightFirefoxBackend()
    config = BrowserGovernorConfig(
        enabled=True,
        execution_enabled=True,
        allowed_profile_ids=["moneybot-default"],
        allowed_hosts=["example.com"],
        profile_root=tmp_path / "profiles",
    )

    with pytest.raises(BrowserAutomationError, match="Playwright Firefox execution failed"):
        backend.execute(config, make_execution_request())


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
