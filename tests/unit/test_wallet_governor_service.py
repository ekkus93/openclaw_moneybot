"""Tests for the wallet governor service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from openclaw_moneybot.plugins.wallet_governor_service import (
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletGovernorService,
    WalletQuoteRequest,
    WalletSendRequest,
)
from openclaw_moneybot.shared import BudgetPlan, Opportunity, PolicyDecision, TosLegalCheck
from openclaw_moneybot.shared.config import MoneyBotPolicyConfig, WalletGovernorConfig
from openclaw_moneybot.shared.types import (
    BudgetDecisionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_service(tmp_path: Path, *, spend_enabled: bool = True) -> WalletGovernorService:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Wallet test",
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
            decision=TosDecisionType.PROCEED,
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
            risk_level=RiskLevel.LOW,
            wallet_spend_request_allowed=True,
            reasons=["Within limits."],
        ),
        idempotency_key="budget:budget_001",
    )
    backend = FakeWalletBackend(FakeWalletBackendState(balance_sats=5_000_000))
    config = WalletGovernorConfig(
        base_url="http://127.0.0.1:8080",
        spend_enabled=spend_enabled,
        allowed_assets=["BTC"],
    )
    policy = MoneyBotPolicyConfig(
        policy_version="v1",
        blocked_categories=["gambling"],
        review_required_categories=["affiliate_marketing"],
        max_single_spend_usd=10,
        max_daily_spend_usd=20,
        max_weekly_spend_usd=40,
    )
    return WalletGovernorService(config, policy, ledger_service, backend)


def make_request(**overrides: object) -> WalletSendRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "budget_plan_id": "budget_001",
        "policy_decision_id": "policy_001",
        "ledger_record_id": "ledger_001",
        "amount_usd": 5.0,
        "asset": "BTC",
        "destination": "bcrt1qexampleaddress",
        "counterparty": "Example Vendor",
        "purpose": "Pay a small approved invoice",
        "category": "purchase",
        "btc_usd_rate": 50_000.0,
        "evidence_archive_ids": ["artifact_001"],
        "idempotency_key": "send_001",
    }
    payload.update(overrides)
    return WalletSendRequest.model_validate(payload)


def test_health_reports_local_state(tmp_path: Path) -> None:
    result = make_service(tmp_path).health()

    assert result.status == "ok"
    assert result.backend == "fake"


def test_quote_returns_btc_and_fee(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    result = service.quote(
        WalletQuoteRequest(
            asset="BTC",
            amount_usd=5.0,
            btc_usd_rate=50_000.0,
            destination="bcrt1qexampleaddress",
        )
    )

    assert result.amount_sats > 0
    assert result.fee_sats > 0


def test_send_rejects_when_spend_disabled(tmp_path: Path) -> None:
    service = make_service(tmp_path, spend_enabled=False)

    result = service.capped_send(make_request())

    assert result.status == "rejected"
    assert result.reason == "spend_disabled"


def test_send_rejects_over_single_limit(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    try:
        service.capped_send(make_request(amount_usd=50.0))
    except ValueError as error:
        assert "single spend" in str(error)
    else:
        raise AssertionError("Expected single-spend limit failure")


def test_send_requires_references() -> None:
    try:
        make_request(ledger_record_id="")
    except ValidationError as error:
        assert "ledger_record_id" in str(error)
    else:
        raise AssertionError("Expected missing ledger reference validation failure")


def test_duplicate_idempotency_returns_same_response(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    first = service.capped_send(make_request())
    second = service.capped_send(make_request())

    assert first.txid == second.txid
    assert second.status == "sent"


def test_successful_send_records_ledger_and_locks_wallet(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    result = service.capped_send(make_request())

    assert result.status == "sent"
    assert result.spend_request_id is not None
    assert result.wallet_transaction_id is not None
    backend = service.backend
    assert isinstance(backend, FakeWalletBackend)
    assert backend.state.lock_count == 1
    assert backend.state.send_count == 1


def test_send_rejects_send_all_request() -> None:
    try:
        make_request(send_all=True)
    except ValidationError as error:
        assert "send_all" in str(error)
    else:
        raise AssertionError("Expected send_all validation failure")
