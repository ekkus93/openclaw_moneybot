"""Integration tests for the default workflow."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from openclaw_moneybot.orchestration import DryRunMissionRequest, MoneyBotOrchestrator
from openclaw_moneybot.plugins.wallet_governor_service import (
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletGovernorService,
    WalletQuoteRequest,
    WalletSendRequest,
)
from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.config import MoneyBotPolicyConfig, WalletGovernorConfig
from openclaw_moneybot.skills.budget_and_roi_planner import BudgetAndRoiPlanner
from openclaw_moneybot.skills.email_drafter import EmailDrafter
from openclaw_moneybot.skills.experiment_reviewer import ExperimentReviewer
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.moneybot_policy_guard import MoneyBotPolicyGuard
from openclaw_moneybot.skills.opportunity_scout import OpportunityScout, ScoutSourceDocument
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.tos_legal_checker import TosLegalChecker
from openclaw_moneybot.skills.wallet_governor_client import WalletGovernorClientSkill


def fixture_text(name: str) -> str:
    return (Path("tests/fixtures/tos_legal") / name).read_text(encoding="utf-8")


def make_wallet_transport(service: WalletGovernorService) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json=service.health().model_dump(mode="json"))
        if request.url.path == "/balance":
            asset = request.url.params.get("asset", "BTC")
            return httpx.Response(200, json=service.balance(asset).model_dump(mode="json"))
        if request.url.path == "/limits":
            asset = request.url.params.get("asset", "BTC")
            return httpx.Response(200, json=service.limits(asset).model_dump(mode="json"))
        if request.url.path == "/quote-spend":
            payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json=service.quote(WalletQuoteRequest.model_validate(payload)).model_dump(mode="json"),
            )
        if request.url.path == "/send-small-payment":
            payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json=service.capped_send(
                    WalletSendRequest.model_validate(payload)
                ).model_dump(mode="json"),
            )
        raise AssertionError(f"Unexpected wallet path: {request.url.path}")

    return httpx.MockTransport(handler)


def make_orchestrator(tmp_path: Path, *, spend_enabled: bool) -> MoneyBotOrchestrator:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = ArchiveConfig(base_directory=tmp_path / "archive")
    policy_config = MoneyBotPolicyConfig(
        policy_version="v1",
        blocked_categories=["gambling"],
        review_required_categories=["affiliate_marketing"],
        max_single_spend_usd=10,
        max_daily_spend_usd=20,
        max_weekly_spend_usd=40,
    )
    wallet_config = WalletGovernorConfig(
        base_url="http://127.0.0.1:8080",
        spend_enabled=spend_enabled,
        allowed_assets=["BTC"],
    )
    wallet_service = WalletGovernorService(
        wallet_config,
        policy_config,
        ledger_service,
        FakeWalletBackend(FakeWalletBackendState(balance_sats=5_000_000)),
    )
    return MoneyBotOrchestrator(
        ledger_service=ledger_service,
        scout=OpportunityScout(),
        policy_guard=MoneyBotPolicyGuard(policy_config),
        tos_checker=TosLegalChecker(ledger_service),
        budget_planner=BudgetAndRoiPlanner(policy_config, ledger_service),
        email_drafter=EmailDrafter(archive_config, ledger_service),
        wallet_client=WalletGovernorClientSkill(
            wallet_config,
            policy_config,
            ledger_service,
            archive_config,
            transport=make_wallet_transport(wallet_service),
        ),
        reviewer=ExperimentReviewer(archive_config, ledger_service),
        archiver=ReceiptAndEvidenceArchiver(archive_config, ledger_service),
    )


def make_source_document() -> ScoutSourceDocument:
    return ScoutSourceDocument(
        source_name="Allowed bounty",
        category_hint="bounty",
        source_url="https://example.com/bounty",
        rules_url="https://example.com/bounty/rules",
        payment_method="BTC payout",
        content_text=(
            fixture_text("allowed_bounty.txt")
            + "\nRequires $5 spend for a hosted preview environment.\nPayout is up to $25."
        ),
    )


def test_dry_run_workflow_creates_full_trail(tmp_path: Path) -> None:
    orchestrator = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        DryRunMissionRequest(
            mission="Review one bounded bounty.",
            source_documents=[make_source_document()],
            draft_recipient_email="maintainer@example.com",
            draft_recipient_name="Maintainer",
            enable_wallet_payment=False,
            current_date=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )

    event_types = {item.event_type for item in result.timeline}

    assert result.dry_run is True
    assert result.wallet_quote is not None
    assert result.wallet_result is None
    assert result.email_draft_id is not None
    assert {
        "opportunity",
        "policy_decision",
        "tos_legal_check",
        "budget_plan",
        "email_draft",
        "experiment_review",
    } <= event_types
    assert result.evidence_archive_ids


def test_wallet_fail_closed_case_is_rejected(tmp_path: Path) -> None:
    orchestrator = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        DryRunMissionRequest(
            mission="Attempt a small approved payment.",
            source_documents=[make_source_document()],
            enable_wallet_payment=True,
            current_date=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )

    event_types = {item.event_type for item in result.timeline}

    assert result.wallet_result is not None
    assert result.wallet_result.status == "rejected"
    assert "wallet_transaction" not in event_types


def test_tiny_capped_payment_path_succeeds(tmp_path: Path) -> None:
    orchestrator = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        DryRunMissionRequest(
            mission="Run a tiny capped payment path.",
            source_documents=[make_source_document()],
            enable_wallet_payment=True,
            current_date=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )

    event_types = {item.event_type for item in result.timeline}

    assert result.wallet_result is not None
    assert result.wallet_result.status == "sent"
    assert "wallet_transaction" in event_types
