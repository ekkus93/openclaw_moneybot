"""Fixture-driven safety regression tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from openclaw_moneybot.plugins.wallet_governor_service import (
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletGovernorService,
    WalletSendRequest,
)
from openclaw_moneybot.shared import BudgetPlan, Opportunity, PolicyDecision, TosLegalCheck
from openclaw_moneybot.shared.config import MoneyBotPolicyConfig, WalletGovernorConfig
from openclaw_moneybot.shared.types import (
    ActionType,
    BudgetDecisionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.moneybot_policy_guard import MoneyBotPolicyGuard, PolicyCheckRequest
from openclaw_moneybot.skills.wallet_governor_client.models import WalletSpendRequest
from openclaw_moneybot.skills.wallet_governor_client.validation import validate_spend_request


def load_fixtures() -> dict[str, list[dict[str, object]]]:
    return cast(
        dict[str, list[dict[str, object]]],
        json.loads(
            Path("tests/fixtures/safety/safety_regressions.json").read_text(encoding="utf-8")
        ),
    )


def make_policy_guard() -> MoneyBotPolicyGuard:
    return MoneyBotPolicyGuard(
        MoneyBotPolicyConfig(
            policy_version="v1",
            blocked_categories=["gambling", "crypto_speculation"],
            review_required_categories=["affiliate_marketing"],
            max_single_spend_usd=10,
            max_daily_spend_usd=20,
            max_weekly_spend_usd=40,
        )
    )


def make_ledger_service(
    tmp_path: Path,
    *,
    tos_decision: TosDecisionType = TosDecisionType.PROCEED,
) -> LedgerService:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Safety fixture test",
            category="bounty",
            status="approved",
            source_url="https://example.com/opportunity",
            rules_url="https://example.com/rules",
            required_spend_usd=0,
            estimated_revenue_usd=25,
            max_loss_usd=5,
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
            source_url="https://example.com/rules",
            decision=tos_decision,
            confidence=ConfidenceLevel.HIGH,
            platform_terms_summary="Proceed.",
            legal_risk_summary="Low.",
            tos_risk_summary="Low.",
            evidence_archive_ids=["artifact_001"],
        ),
        idempotency_key="tos:tos_001",
    )
    ledger_service.record_budget_plan(
        BudgetPlan(
            created_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
            budget_plan_id="budget_001",
            opportunity_id="opp_001",
            policy_decision_id="policy_001",
            tos_legal_check_id="tos_001",
            decision=BudgetDecisionType.EXECUTE_REQUEST,
            recommended_budget_usd=5,
            max_loss_usd=5,
            expected_gross_revenue_usd=20,
            expected_net_revenue_usd=15,
            break_even_condition="One payout",
            success_metric="Paid",
            stop_condition="Stop after one try",
            required_records=["budget_snapshot"],
            required_evidence_ids=[],
            risk_level=RiskLevel.LOW,
            wallet_spend_request_allowed=True,
            approved_spend_categories=["purchase", "listing_fee"],
            reasons=["Within limits."],
        ),
        idempotency_key="budget:budget_001",
    )
    return ledger_service


def make_wallet_request(**overrides: object) -> WalletSpendRequest:
    payload: dict[str, object] = {
        "spend_request_id": "spend_001",
        "opportunity_id": "opp_001",
        "policy_decision_id": "policy_001",
        "budget_plan_id": "budget_001",
        "tos_legal_check_id": "tos_001",
        "ledger_event_id": "ledger_001",
        "amount_usd": 5.0,
        "asset": "BTC",
        "destination": "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
        "counterparty": "Example Vendor",
        "purpose": "Pay approved listing fee",
        "category": "listing_fee",
        "evidence_archive_ids": ["artifact_001"],
        "btc_usd_rate": 50_000.0,
        "idempotency_key": "fixture_send_001",
    }
    payload.update(overrides)
    return WalletSpendRequest.model_validate(payload)


@pytest.mark.parametrize("case", load_fixtures()["policy_cases"])
def test_policy_regression_fixtures(case: dict[str, object]) -> None:
    guard = make_policy_guard()
    request = PolicyCheckRequest.model_validate(
        {
            "action_id": "action_fixture",
            "action_type": ActionType.RESEARCH,
            "title": str(case["name"]),
            "description": str(case["description"]),
            "category": str(case["category"]),
            "source_urls": ["https://example.com"],
            "planned_tools": [],
            "metadata": {"opportunity_id": "opp_001"},
        }
    )

    result = guard.evaluate(request)

    assert result.decision is PolicyDecisionType.BLOCK
    assert str(case["expected_rule"]) in result.matched_rules


def test_send_all_wallet_fixture_blocks(tmp_path: Path) -> None:
    ledger_service = make_ledger_service(tmp_path)
    reasons = validate_spend_request(
        make_wallet_request(purpose="Send all funds now"),
        WalletGovernorConfig(
            base_url="http://127.0.0.1:8080",
            spend_enabled=True,
            allowed_assets=["BTC"],
        ),
        make_policy_guard().config,
        ledger_service,
    )

    assert "send-all language is prohibited" in reasons


def test_tos_human_review_wallet_fixture_blocks(tmp_path: Path) -> None:
    ledger_service = make_ledger_service(tmp_path, tos_decision=TosDecisionType.HUMAN_REVIEW)
    reasons = validate_spend_request(
        make_wallet_request(),
        WalletGovernorConfig(
            base_url="http://127.0.0.1:8080",
            spend_enabled=True,
            allowed_assets=["BTC"],
        ),
        make_policy_guard().config,
        ledger_service,
    )

    assert "autonomous wallet spend requires tos/legal proceed" in reasons


def test_blocked_category_wallet_fixture_blocks(tmp_path: Path) -> None:
    ledger_service = make_ledger_service(tmp_path)
    reasons = validate_spend_request(
        make_wallet_request(category="gambling"),
        WalletGovernorConfig(
            base_url="http://127.0.0.1:8080",
            spend_enabled=True,
            allowed_assets=["BTC"],
        ),
        make_policy_guard().config,
        ledger_service,
    )

    assert "blocked spend category" in reasons


def test_missing_prewrite_wallet_fixture_blocks(tmp_path: Path) -> None:
    ledger_service = make_ledger_service(tmp_path)
    service = WalletGovernorService(
        WalletGovernorConfig(
            base_url="http://127.0.0.1:8080",
            spend_enabled=True,
            allowed_assets=["BTC"],
        ),
        make_policy_guard().config,
        ledger_service,
        FakeWalletBackend(FakeWalletBackendState(balance_sats=5_000_000)),
    )
    request = WalletSendRequest.model_validate(
        {
            "spend_request_id": "missing_spend",
            "opportunity_id": "opp_001",
            "budget_plan_id": "budget_001",
            "policy_decision_id": "policy_001",
            "ledger_record_id": "ledger_001",
            "amount_usd": 5.0,
            "asset": "BTC",
            "destination": "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
            "counterparty": "Example Vendor",
            "purpose": "Pay approved listing fee",
            "category": "purchase",
            "btc_usd_rate": 50_000.0,
            "evidence_archive_ids": ["artifact_001"],
            "idempotency_key": "fixture_service_send_001",
        }
    )

    result = service.capped_send(request)

    assert result.reason == "spend_request_not_found"
