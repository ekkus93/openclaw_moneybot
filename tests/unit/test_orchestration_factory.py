"""Tests for orchestrator factory wiring."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx

from openclaw_moneybot.orchestration.factory import build_orchestrator
from openclaw_moneybot.orchestration.workflow import MoneyBotOrchestrator
from openclaw_moneybot.shared import (
    AppConfig,
    ArchiveConfig,
    BrowserGovernorConfig,
    EmailConfig,
    LedgerConfig,
    MoneyBotPolicyConfig,
    WalletGovernorConfig,
)
from openclaw_moneybot.skills.budget_and_roi_planner import BudgetAndRoiPlanner
from openclaw_moneybot.skills.email_drafter import EmailDrafter
from openclaw_moneybot.skills.experiment_reviewer import ExperimentReviewer
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.moneybot_policy_guard import MoneyBotPolicyGuard
from openclaw_moneybot.skills.opportunity_scout import OpportunityScout
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.tos_legal_checker import TosLegalChecker
from openclaw_moneybot.skills.wallet_governor_client import WalletGovernorClientSkill


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        policy=MoneyBotPolicyConfig(
            policy_version="v1",
            blocked_categories=["gambling"],
            review_required_categories=["affiliate_marketing"],
            max_single_spend_usd=10,
            max_daily_spend_usd=20,
            max_weekly_spend_usd=40,
        ),
        ledger=LedgerConfig(database_path=tmp_path / "data" / "moneybot.sqlite3"),
        archive=ArchiveConfig(base_directory=tmp_path / "archive"),
        wallet_governor=WalletGovernorConfig(base_url="http://127.0.0.1:8080"),
        email=EmailConfig(),
        browser_governor=BrowserGovernorConfig(),
    )


def test_build_orchestrator_returns_moneybot_orchestrator(tmp_path: Path) -> None:
    orchestrator = build_orchestrator(make_config(tmp_path))

    assert isinstance(orchestrator, MoneyBotOrchestrator)


def test_build_orchestrator_wires_expected_component_types(tmp_path: Path) -> None:
    orchestrator = build_orchestrator(make_config(tmp_path))

    assert isinstance(orchestrator.ledger_service, LedgerService)
    assert isinstance(orchestrator.scout, OpportunityScout)
    assert isinstance(orchestrator.policy_guard, MoneyBotPolicyGuard)
    assert isinstance(orchestrator.tos_checker, TosLegalChecker)
    assert isinstance(orchestrator.budget_planner, BudgetAndRoiPlanner)
    assert isinstance(orchestrator.email_drafter, EmailDrafter)
    assert isinstance(orchestrator.wallet_client, WalletGovernorClientSkill)
    assert isinstance(orchestrator.reviewer, ExperimentReviewer)
    assert isinstance(orchestrator.archiver, ReceiptAndEvidenceArchiver)


def test_build_orchestrator_passes_optional_wallet_transport(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "ok"}))

    orchestrator = build_orchestrator(make_config(tmp_path), wallet_transport=transport)

    assert orchestrator.wallet_client.http_client._client._transport is transport


def test_factory_created_ledger_path_exists_and_is_migrated(tmp_path: Path) -> None:
    config = make_config(tmp_path)

    build_orchestrator(config)

    assert config.ledger.database_path.exists() is True
    with sqlite3.connect(config.ledger.database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "ledger_events" in tables
