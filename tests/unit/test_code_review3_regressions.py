"""Focused regression tests for Code Review 3 fixes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from openclaw_moneybot.plugins.wallet_governor_service import (
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletGovernorService,
    WalletQuoteRequest,
    WalletSendRequest,
)
from openclaw_moneybot.plugins.wallet_governor_service.backend import WalletBackendError
from openclaw_moneybot.shared import (
    BudgetPlan,
    EvidenceRecord,
    LedgerRecord,
    MoneyBotPolicyConfig,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    TosLegalCheck,
    WalletGovernorConfig,
    WalletTransactionRecord,
)
from openclaw_moneybot.shared.types import (
    ActionType,
    BudgetDecisionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RecordType,
    RiskLevel,
    TosDecisionType,
    WalletTransactionStatus,
)
from openclaw_moneybot.skills.ledger_skill.repository import LedgerRepository
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver.hashing import sha256_bytes
from openclaw_moneybot.utils.time import utc_now


def test_invalid_btc_like_quote_and_send_destinations_are_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service, destination="bc1notvalid!!!!")
    bundle = service.ledger_service.get_spend_authorization_bundle("spend_001")
    assert bundle is not None
    bundle.spend_request = bundle.spend_request.model_copy(
        update={"destination": "bc1notvalid!!!!"}
    )
    service.ledger_service.get_spend_authorization_bundle = (  # type: ignore[method-assign]
        lambda spend_request_id: bundle if spend_request_id == "spend_001" else None
    )
    quote = service.quote(
        WalletQuoteRequest(
            asset="BTC",
            amount_usd=5.0,
            btc_usd_rate=50_000.0,
            destination="bc1notvalid!!!!",
        )
    )
    send = service.capped_send(request)

    assert quote.reason == "destination_invalid"
    assert send.reason == "destination_invalid"


def test_balance_failure_audit_regression(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    service.backend.get_balance_sats = (  # type: ignore[method-assign]
        lambda: (_ for _ in ()).throw(WalletBackendError("boom"))
    )

    result = service.capped_send(request)
    events = service.ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
    )

    assert result.reason == "backend_error"
    assert any(
        isinstance(event.payload.get("payload"), dict)
        and event.payload.get("related_record_id") == "spend_001"
        and cast(dict[str, object], event.payload["payload"]).get("event_name")
        == "wallet_backend_balance_failed"
        for event in events
    )


def test_satoshi_aggregation_regression(tmp_path: Path) -> None:
    repository = LedgerRepository(tmp_path / "code-review3.sqlite3")
    try:
        repository.migrate()
        base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        repository.create_opportunity(make_opportunity(base_time))
        repository.record_policy_decision(make_policy(base_time + timedelta(minutes=1)))
        repository.record_tos_legal_check(make_tos_check(base_time + timedelta(minutes=2)))
        repository.record_budget_plan(make_budget_plan(base_time + timedelta(minutes=3)))
        repository.record_spend_request(make_spend_request(base_time + timedelta(minutes=4)))
        repository.record_btc_transaction(
            WalletTransactionRecord(
                created_at=base_time + timedelta(minutes=5),
                wallet_transaction_id="wallet_tx_regression",
                spend_request_id="spend_001",
                txid="tx_regression",
                amount_btc="0.00000003",
                fee_btc="0.00000005",
                amount_usd_estimate=0.03,
                fee_usd_estimate=0.05,
                total_usd_estimate=0.08,
                status=WalletTransactionStatus.SENT,
                destination="bc1qqqgjyv6y24n80zye42aueh0wluqpzg3ndy2ehs",
                purpose="Regression",
            )
        )

        totals = repository.get_experiment_spend_total("exp_001")

        assert totals.amount_sats == 3
        assert totals.fee_sats == 5
        assert totals.amount_btc == "0.00000003"
        assert totals.fee_btc == "0.00000005"
    finally:
        if repository.db_path.exists():
            repository.db_path.unlink()


def make_service(tmp_path: Path) -> WalletGovernorService:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_root = tmp_path / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    evidence_path = archive_root / "artifact_001.html"
    evidence_bytes = b"code review 3 regression evidence"
    evidence_path.write_bytes(evidence_bytes)
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Regression wallet test",
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
            action_type=ActionType.SPEND,
            category="purchase",
            requires_payment=True,
            requires_wallet_action=True,
            amount_usd=100.0,
            counterparty="Example Vendor",
            planned_tools=["wallet_governor_client"],
            sanitized_input={"action_type": "spend"},
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
    ledger_service.record_evidence(
        EvidenceRecord(
            created_at=datetime(2026, 1, 1, 0, 4, tzinfo=UTC),
            evidence_id="artifact_001",
            related_record_type=RecordType.OPPORTUNITY,
            related_record_id="opp_001",
            evidence_type="html_snapshot",
            archive_path=str(evidence_path),
            content_sha256=sha256_bytes(evidence_bytes),
            source_url="https://example.com/opportunity",
        ),
        idempotency_key="evidence:artifact_001",
    )
    prewrite = ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=utc_now(),
            record_id="audit_prewrite_001",
            record_type=RecordType.AUDIT_EVENT,
            related_record_id="spend_001",
            payload={"event_name": "wallet_prewrite"},
        ),
        idempotency_key="prewrite:spend_001",
    )
    ledger_service.record_spend_request(
        SpendRequest(
            created_at=utc_now(),
            spend_request_id="spend_001",
            opportunity_id="opp_001",
            budget_plan_id="budget_001",
            policy_decision_id="policy_001",
            ledger_record_id=prewrite.ledger_event_id,
            amount_usd=5.0,
            asset="BTC",
            destination="bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
            counterparty="Example Vendor",
            purpose="Approved small payment",
            category="purchase",
            evidence_archive_ids=["artifact_001"],
            status="proposed",
        ),
        idempotency_key="spend:spend_001",
    )
    return WalletGovernorService(
        WalletGovernorConfig(
            base_url="http://127.0.0.1:8080",
            spend_enabled=True,
            allowed_assets=["BTC"],
            archive_root=archive_root,
        ),
        MoneyBotPolicyConfig(
            policy_version="v1",
            blocked_categories=["gambling"],
            review_required_categories=["affiliate_marketing"],
            max_single_spend_usd=10,
            max_daily_spend_usd=20,
            max_weekly_spend_usd=40,
        ),
        ledger_service,
        FakeWalletBackend(FakeWalletBackendState(balance_sats=5_000_000)),
    )


def seed_spend_request(service: WalletGovernorService, **overrides: object) -> WalletSendRequest:
    spend_request = service.ledger_service.get_spend_request("spend_001")
    assert spend_request is not None
    request = WalletSendRequest.model_validate(
        {
            "spend_request_id": "spend_001",
            "opportunity_id": "opp_001",
            "budget_plan_id": "budget_001",
            "policy_decision_id": "policy_001",
            "ledger_record_id": spend_request.ledger_record_id,
            "amount_usd": 5.0,
            "asset": "BTC",
            "destination": "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
            "counterparty": "Example Vendor",
            "purpose": "Approved small payment",
            "category": "purchase",
            "btc_usd_rate": 50_000.0,
            "evidence_archive_ids": ["artifact_001"],
            "idempotency_key": "send_001",
        }
    )
    return request.model_copy(update=overrides)


def make_opportunity(created_at: datetime) -> Opportunity:
    return Opportunity(
        created_at=created_at,
        opportunity_id="opp_001",
        name="OSS bounty",
        category="bounty",
        status="discovered",
        source_url="https://example.com/opportunity",
        rules_url="https://example.com/rules",
        required_spend_usd=0,
        estimated_revenue_usd=25,
        max_loss_usd=0,
    )


def make_policy(created_at: datetime) -> PolicyDecision:
    return PolicyDecision(
        created_at=created_at,
        policy_decision_id="policy_001",
        opportunity_id="opp_001",
        decision=PolicyDecisionType.ALLOW,
        risk_level=RiskLevel.LOW,
        confidence=ConfidenceLevel.HIGH,
        matched_rules=["safe_research"],
        policy_version="v1",
        request_fingerprint="req_hash",
    )


def make_tos_check(created_at: datetime) -> TosLegalCheck:
    return TosLegalCheck(
        created_at=created_at,
        tos_legal_check_id="tos_001",
        opportunity_id="opp_001",
        decision=TosDecisionType.PROCEED,
        confidence=ConfidenceLevel.HIGH,
        platform_terms_summary="Terms allow submissions.",
        legal_risk_summary="No obvious legal risk.",
        tos_risk_summary="Low risk.",
        evidence_archive_ids=["artifact_001"],
    )


def make_budget_plan(created_at: datetime) -> BudgetPlan:
    return BudgetPlan(
        created_at=created_at,
        budget_plan_id="budget_001",
        opportunity_id="opp_001",
        policy_decision_id="policy_001",
        tos_legal_check_id="tos_001",
        decision=BudgetDecisionType.EXECUTE_REQUEST,
        recommended_budget_usd=5,
        max_loss_usd=5,
        expected_gross_revenue_usd=20,
        expected_net_revenue_usd=15,
        break_even_condition="One accepted bounty.",
        success_metric="Accepted submission",
        stop_condition="Stop after one rejection.",
        required_records=["receipt"],
        risk_level=RiskLevel.LOW,
        wallet_spend_request_allowed=True,
    )


def make_spend_request(created_at: datetime) -> SpendRequest:
    return SpendRequest(
        created_at=created_at,
        spend_request_id="spend_001",
        opportunity_id="opp_001",
        experiment_id="exp_001",
        budget_plan_id="budget_001",
        policy_decision_id="policy_001",
        ledger_record_id="ledger_prewrite_001",
        amount_usd=5,
        asset="BTC",
        destination="bc1qqqgjyv6y24n80zye42aueh0wluqpzg3ndy2ehs",
        counterparty="Example registrar",
        purpose="Buy domain",
        category="infrastructure",
        evidence_archive_ids=["artifact_001"],
    )
