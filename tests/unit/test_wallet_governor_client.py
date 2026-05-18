"""Tests for the wallet governor client skill."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from openclaw_moneybot.shared import (
    ArchiveConfig,
    BudgetPlan,
    Opportunity,
    PolicyDecision,
    TosLegalCheck,
    WalletTransactionRecord,
)
from openclaw_moneybot.shared.config import MoneyBotPolicyConfig, WalletGovernorConfig
from openclaw_moneybot.shared.types import (
    BudgetDecisionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.wallet_governor_client import (
    WalletBalanceRequest,
    WalletGovernorClientSkill,
    WalletQuoteSkillRequest,
    WalletSpendRequest,
)


def make_skill(
    tmp_path: Path,
    *,
    spend_enabled: bool = True,
    handler: httpx.MockTransport | None = None,
) -> WalletGovernorClientSkill:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Wallet client test",
            category="bounty",
            status="approved",
            source_url="https://example.com/opportunity",
            rules_url="https://example.com/rules",
            required_spend_usd=0,
            estimated_revenue_usd=50,
            max_loss_usd=8,
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
            recommended_budget_usd=8,
            max_loss_usd=8,
            expected_gross_revenue_usd=50,
            expected_net_revenue_usd=42,
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
    transport = handler or httpx.MockTransport(default_handler)
    return WalletGovernorClientSkill(
        config,
        policy,
        ledger_service,
        ArchiveConfig(base_directory=tmp_path / "archive"),
        transport=transport,
    )


def default_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/balance":
        return httpx.Response(
            200,
            json={
                "asset": "BTC",
                "balance_btc": "0.01000000",
                "balance_sats": 1_000_000,
            },
        )
    if request.url.path == "/limits":
        return httpx.Response(
            200,
            json={
                "asset": "BTC",
                "spend_enabled": True,
                "max_single_usd": 10.0,
                "max_daily_usd": 20.0,
                "max_weekly_usd": 40.0,
                "remaining_daily_usd": 20.0,
                "remaining_weekly_usd": 40.0,
            },
        )
    if request.url.path == "/quote-spend":
        return httpx.Response(
            200,
            json={
                "asset": "BTC",
                "amount_btc": "0.00010000",
                "amount_sats": 10_000,
                "fee_btc": "0.00000250",
                "fee_sats": 250,
                "amount_usd": 5.0,
                "estimated_fee_usd": 0.12,
                "total_usd_estimate": 5.12,
                "total_usd": 5.12,
            },
        )
    if request.url.path == "/send-small-payment":
        payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "status": "sent",
                "spend_request_id": payload["spend_request_id"],
                "wallet_transaction_id": "wallet_tx_001",
                "txid": "tx_001",
                "amount_btc": "0.00010000",
                "fee_btc": "0.00000250",
                "amount_usd": payload["amount_usd"],
            },
        )
    raise AssertionError(f"Unexpected path: {request.url.path}")


def make_spend_request(**overrides: object) -> WalletSpendRequest:
    payload: dict[str, object] = {
        "spend_request_id": "spend_001",
        "opportunity_id": "opp_001",
        "policy_decision_id": "policy_001",
        "budget_plan_id": "budget_001",
        "tos_legal_check_id": "tos_001",
        "ledger_event_id": "2026-01-01T00:00:00Z",
        "amount_usd": 5.0,
        "asset": "BTC",
        "destination": "bcrt1qmoneybotdest123",
        "counterparty": "Example Vendor",
        "purpose": "Pay approved listing fee",
        "category": "listing_fee",
        "evidence_archive_ids": ["artifact_001"],
        "btc_usd_rate": 50_000.0,
        "idempotency_key": "client_send_001",
    }
    payload.update(overrides)
    return WalletSpendRequest.model_validate(payload)


def test_read_only_balance_call(tmp_path: Path) -> None:
    skill = make_skill(tmp_path)

    result = skill.get_balance(WalletBalanceRequest(asset="BTC", btc_usd_rate=50_000.0))

    assert result.asset == "BTC"
    assert result.usd_estimate == 500.0


def test_spend_disabled_mode_blocks_spend(tmp_path: Path) -> None:
    skill = make_skill(tmp_path, spend_enabled=False)

    result = skill.spend(make_spend_request())

    assert result.status == "rejected"
    assert "spend disabled" in result.rejection_reasons


def test_missing_policy_id_blocks_spend_before_http_call(tmp_path: Path) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return default_handler(request)

    skill = make_skill(tmp_path, handler=httpx.MockTransport(handler))
    result = skill.spend(make_spend_request(policy_decision_id="policy_missing"))

    assert result.status == "rejected"
    assert "missing policy approval" in result.rejection_reasons
    assert called is False


def test_missing_budget_plan_blocks_spend_before_http_call(tmp_path: Path) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return default_handler(request)

    skill = make_skill(tmp_path, handler=httpx.MockTransport(handler))
    result = skill.spend(make_spend_request(budget_plan_id="budget_missing"))

    assert result.status == "rejected"
    assert "missing budget plan" in result.rejection_reasons
    assert called is False


def test_over_limit_amount_blocks_spend_before_http_call(tmp_path: Path) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return default_handler(request)

    skill = make_skill(tmp_path, handler=httpx.MockTransport(handler))
    result = skill.spend(make_spend_request(amount_usd=50.0))

    assert result.status == "rejected"
    assert "amount exceeds single-spend cap" in result.rejection_reasons
    assert called is False


def test_service_rejection_is_preserved_and_recorded(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/send-small-payment":
            return httpx.Response(
                200,
                json={"status": "rejected", "rejection_reasons": ["service policy block"]},
            )
        return default_handler(request)

    skill = make_skill(tmp_path, handler=httpx.MockTransport(handler))
    result = skill.spend(make_spend_request())

    assert result.status == "rejected"
    assert "service policy block" in result.rejection_reasons
    assert result.raw_response_evidence_id is not None


def test_service_timeout_returns_safe_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/send-small-payment":
            raise httpx.ConnectTimeout("timed out")
        return default_handler(request)

    skill = make_skill(tmp_path, handler=httpx.MockTransport(handler))
    result = skill.spend(make_spend_request())

    assert result.status == "error"
    assert "wallet governor unavailable" in result.rejection_reasons


def test_no_retry_on_spend_by_default(tmp_path: Path) -> None:
    send_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal send_attempts
        if request.url.path == "/send-small-payment":
            send_attempts += 1
            raise httpx.ConnectError("boom")
        return default_handler(request)

    skill = make_skill(tmp_path, handler=httpx.MockTransport(handler))
    skill.spend(make_spend_request())

    assert send_attempts == 1


def test_valid_spend_request_serialization_and_success(tmp_path: Path) -> None:
    skill = make_skill(tmp_path)
    ledger_service = skill.ledger_service

    def send_and_record(payload: dict[str, object]) -> dict[str, object]:
        ledger_service.record_wallet_transaction(
            WalletTransactionRecord(
                created_at=datetime.now(tz=UTC),
                wallet_transaction_id="wallet_tx_001",
                spend_request_id=str(payload["spend_request_id"]),
                txid="tx_001",
                amount_btc="0.00010000",
                fee_btc="0.00000250",
                amount_usd_estimate=5.0,
                status="sent",
                destination=str(payload["destination"]),
                purpose=str(payload["purpose"]),
            ),
            idempotency_key="wallet:tx:client_send_001",
        )
        return {
            "status": "sent",
            "spend_request_id": str(payload["spend_request_id"]),
            "wallet_transaction_id": "wallet_tx_001",
            "txid": "tx_001",
            "amount_btc": "0.00010000",
            "fee_btc": "0.00000250",
            "amount_usd": 5.0,
        }

    skill.http_client.send_small_payment = send_and_record  # type: ignore[assignment]
    result = skill.spend(make_spend_request())

    assert result.status == "sent"
    assert result.txid_or_signature == "tx_001"
    assert result.ledger_recorded is True


def test_quote_serialization(tmp_path: Path) -> None:
    skill = make_skill(tmp_path)

    result = skill.quote(
        WalletQuoteSkillRequest(
            asset="BTC",
            amount_usd=5.0,
            destination="bcrt1qmoneybotdest123",
            btc_usd_rate=50_000.0,
        )
    )

    assert result.status == "ok"
    assert result.amount_asset_estimate == "0.00010000"
