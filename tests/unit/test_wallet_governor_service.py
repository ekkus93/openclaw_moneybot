"""Tests for the wallet governor service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from openclaw_moneybot.plugins.wallet_governor_service import (
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletGovernorService,
    WalletQuoteRequest,
    WalletQuoteResponse,
    WalletSendRequest,
)
from openclaw_moneybot.plugins.wallet_governor_service.backend import WalletBackendError
from openclaw_moneybot.shared import (
    BudgetPlan,
    EvidenceRecord,
    LedgerRecord,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    SpendRequestStatus,
    TosLegalCheck,
    WalletTransactionRecord,
    WalletTransactionStatus,
)
from openclaw_moneybot.shared.config import MoneyBotPolicyConfig, WalletGovernorConfig
from openclaw_moneybot.shared.types import (
    ActionType,
    BudgetDecisionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RecordType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.ledger_skill.models import SpendAuthorizationBundle
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver.hashing import sha256_bytes
from openclaw_moneybot.utils.time import utc_now

Mutator = Callable[
    [WalletSendRequest, SpendAuthorizationBundle, WalletGovernorService],
    None,
]


def make_service(tmp_path: Path, *, spend_enabled: bool = True) -> WalletGovernorService:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_root = tmp_path / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    evidence_path = archive_root / "artifact_001.html"
    evidence_bytes = b"wallet test evidence"
    evidence_path.write_bytes(evidence_bytes)
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
    backend = FakeWalletBackend(FakeWalletBackendState(balance_sats=5_000_000))
    config = WalletGovernorConfig(
        base_url="http://127.0.0.1:8080",
        spend_enabled=spend_enabled,
        allowed_assets=["BTC"],
        archive_root=archive_root,
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
        "spend_request_id": "spend_001",
        "opportunity_id": "opp_001",
        "budget_plan_id": "budget_001",
        "policy_decision_id": "policy_001",
        "ledger_record_id": "ledger_001",
        "amount_usd": 5.0,
        "asset": "BTC",
        "destination": "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
        "counterparty": "Example Vendor",
        "purpose": "Pay a small approved invoice",
        "category": "purchase",
        "btc_usd_rate": 50_000.0,
        "evidence_archive_ids": ["artifact_001"],
        "idempotency_key": "send_001",
    }
    payload.update(overrides)
    return WalletSendRequest.model_validate(payload)


def seed_spend_request(
    service: WalletGovernorService,
    **overrides: object,
) -> WalletSendRequest:
    request = make_request(**overrides)
    prewrite = service.ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=utc_now(),
            record_id="audit_prewrite_001",
            record_type=RecordType.AUDIT_EVENT,
            related_record_id=request.spend_request_id,
            payload={"event_name": "wallet_prewrite"},
        ),
        idempotency_key=f"prewrite:{request.spend_request_id}",
    )
    service.ledger_service.record_spend_request(
        SpendRequest(
            created_at=utc_now(),
            spend_request_id=request.spend_request_id,
            opportunity_id=request.opportunity_id,
            experiment_id=request.experiment_id,
            budget_plan_id=request.budget_plan_id,
            policy_decision_id=request.policy_decision_id,
            ledger_record_id=prewrite.ledger_event_id,
            amount_usd=request.amount_usd,
            asset=request.asset,
            destination=request.destination,
            counterparty=request.counterparty,
            purpose=request.purpose,
            category=request.category,
            evidence_archive_ids=request.evidence_archive_ids,
            status="proposed",
        ),
        idempotency_key=f"spend:{request.spend_request_id}",
    )
    return request.model_copy(update={"ledger_record_id": prewrite.ledger_event_id})


def seed_spend_without_prewrite(
    service: WalletGovernorService,
    **overrides: object,
) -> WalletSendRequest:
    request = make_request(**overrides)
    service.ledger_service.record_spend_request(
        SpendRequest(
            created_at=utc_now(),
            spend_request_id=request.spend_request_id,
            opportunity_id=request.opportunity_id,
            experiment_id=request.experiment_id,
            budget_plan_id=request.budget_plan_id,
            policy_decision_id=request.policy_decision_id,
            ledger_record_id=request.ledger_record_id,
            amount_usd=request.amount_usd,
            asset=request.asset,
            destination=request.destination,
            counterparty=request.counterparty,
            purpose=request.purpose,
            category=request.category,
            evidence_archive_ids=request.evidence_archive_ids,
            status="proposed",
        ),
        idempotency_key=f"spend:{request.spend_request_id}",
    )
    return request


def get_bundle(
    service: WalletGovernorService,
    request: WalletSendRequest,
) -> SpendAuthorizationBundle:
    bundle = service.ledger_service.get_spend_authorization_bundle(request.spend_request_id or "")
    assert bundle is not None
    return bundle


def assert_reason_for_mutated_bundle(
    service: WalletGovernorService,
    request: WalletSendRequest,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mutate: Mutator,
    expected_reason: str,
) -> None:
    bundle = get_bundle(service, request)
    mutate(request, bundle, service)
    monkeypatch.setattr(
        service.ledger_service,
        "get_spend_authorization_bundle",
        lambda spend_request_id: bundle if spend_request_id == request.spend_request_id else None,
    )

    result = service.capped_send(request)

    assert result.status == "rejected"
    assert result.reason == expected_reason


def sync_request_and_spend_request(field: str, value: object) -> Mutator:
    def _mutate(
        request: WalletSendRequest,
        bundle: SpendAuthorizationBundle,
        service: WalletGovernorService,
    ) -> None:
        del service
        setattr(request, field, value)
        bundle.spend_request = bundle.spend_request.model_copy(update={field: value})

    return _mutate


def block_policy_category(value: str) -> Mutator:
    def _mutate(
        request: WalletSendRequest,
        bundle: SpendAuthorizationBundle,
        service: WalletGovernorService,
    ) -> None:
        service.policy_config.blocked_categories.append(value)
        sync_category_everywhere(value)(request, bundle, service)

    return _mutate


def sync_category_everywhere(value: str) -> Mutator:
    def _mutate(
        request: WalletSendRequest,
        bundle: SpendAuthorizationBundle,
        service: WalletGovernorService,
    ) -> None:
        sync_request_and_spend_request("category", value)(request, bundle, service)
        assert bundle.policy_decision is not None
        bundle.policy_decision = bundle.policy_decision.model_copy(update={"category": value})

    return _mutate


def update_policy(**changes: object) -> Mutator:
    def _mutate(
        request: WalletSendRequest,
        bundle: SpendAuthorizationBundle,
        service: WalletGovernorService,
    ) -> None:
        del request, service
        assert bundle.policy_decision is not None
        bundle.policy_decision = bundle.policy_decision.model_copy(update=changes)

    return _mutate


def update_budget(**changes: object) -> Mutator:
    def _mutate(
        request: WalletSendRequest,
        bundle: SpendAuthorizationBundle,
        service: WalletGovernorService,
    ) -> None:
        del request, service
        assert bundle.budget_plan is not None
        bundle.budget_plan = bundle.budget_plan.model_copy(update=changes)

    return _mutate


def update_tos(**changes: object) -> Mutator:
    def _mutate(
        request: WalletSendRequest,
        bundle: SpendAuthorizationBundle,
        service: WalletGovernorService,
    ) -> None:
        del request, service
        assert bundle.tos_legal_check is not None
        bundle.tos_legal_check = bundle.tos_legal_check.model_copy(update=changes)

    return _mutate


def set_unrelated_evidence(
    request: WalletSendRequest,
    bundle: SpendAuthorizationBundle,
    service: WalletGovernorService,
) -> None:
    del service
    request.evidence_archive_ids = ["artifact_unrelated"]
    assert bundle.tos_legal_check is not None
    bundle.tos_legal_check = bundle.tos_legal_check.model_copy(
        update={"evidence_archive_ids": ["artifact_unrelated"]}
    )
    bundle.spend_request = bundle.spend_request.model_copy(
        update={"evidence_archive_ids": ["artifact_unrelated"]}
    )
    bundle.evidence_records = [
        EvidenceRecord(
            created_at=utc_now(),
            evidence_id="artifact_unrelated",
            related_record_type=RecordType.OPPORTUNITY,
            related_record_id="opp_else",
            evidence_type="html_snapshot",
            archive_path="archive/unrelated.html",
            content_sha256="b" * 64,
        )
    ]


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
            destination="bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
        )
    )

    assert result.amount_sats is not None
    assert result.fee_sats is not None
    assert result.amount_sats > 0
    assert result.fee_sats > 0


def test_quote_rejects_invalid_destination(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    result = service.quote(
        WalletQuoteRequest(
            asset="BTC",
            amount_usd=5.0,
            btc_usd_rate=50_000.0,
            destination="not-a-btc-address",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "destination_invalid"
    backend = service.backend
    assert isinstance(backend, FakeWalletBackend)
    assert backend.state.last_unlock_seconds == 0
    assert backend.state.send_count == 0


def test_quote_accepts_network_specific_addresses(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    regtest_result = service.quote(
        WalletQuoteRequest(
            asset="BTC",
            amount_usd=5.0,
            btc_usd_rate=50_000.0,
            destination="bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
        )
    )
    service.config.bitcoin_network = "mainnet"  # type: ignore[assignment]
    mainnet_result = service.quote(
        WalletQuoteRequest(
            asset="BTC",
            amount_usd=5.0,
            btc_usd_rate=50_000.0,
            destination="1BoatSLRHtKNngkdXEeobR76b53LETtpyT",
        )
    )

    assert regtest_result.status == "ok"
    assert mainnet_result.status == "ok"


def test_quote_rejects_network_mismatch_and_unknown_network(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.config.bitcoin_network = "mainnet"  # type: ignore[assignment]

    mismatch = service.quote(
        WalletQuoteRequest(
            asset="BTC",
            amount_usd=5.0,
            btc_usd_rate=50_000.0,
            destination="tb1qqqgjyv6y24n80zye42aueh0wluqpzg3n8z32vr",
        )
    )
    service.config.bitcoin_network = "broken"  # type: ignore[assignment]
    unknown = service.quote(
        WalletQuoteRequest(
            asset="BTC",
            amount_usd=5.0,
            btc_usd_rate=50_000.0,
            destination="1BoatSLRHtKNngkdXEeobR76b53LETtpyT",
        )
    )

    assert mismatch.reason == "destination_invalid"
    assert unknown.reason == "destination_invalid"


def test_quote_rejects_blocklisted_destination(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.config.blocked_destinations = ["bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2"]

    result = service.quote(
        WalletQuoteRequest(
            asset="BTC",
            amount_usd=5.0,
            btc_usd_rate=50_000.0,
            destination="bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "destination_blocked"


def test_send_rejects_when_spend_disabled(tmp_path: Path) -> None:
    service = make_service(tmp_path, spend_enabled=False)

    result = service.capped_send(seed_spend_request(service))

    assert result.status == "rejected"
    assert result.reason == "spend_disabled"


def test_send_rejects_blocklisted_destination_and_records_audit(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.config.blocked_destinations = ["bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2"]

    result = service.capped_send(seed_spend_request(service))
    backend = service.backend
    assert isinstance(backend, FakeWalletBackend)

    events = service.ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
    )

    assert result.status == "rejected"
    assert result.reason == "destination_blocked"
    assert backend.state.send_count == 0
    assert any(
        isinstance(event.payload.get("payload"), dict)
        and event.payload.get("related_record_id") == "spend_001"
        and cast(dict[str, object], event.payload["payload"]).get("event_name")
        == "wallet_send_rejected"
        and cast(dict[str, object], event.payload["payload"]).get("reason_code")
        == "destination_blocked"
        for event in events
    )


@pytest.mark.parametrize("evidence_type", ["random_note", "scratchpad", "debug_dump"])
def test_send_rejects_disallowed_evidence_type_before_backend(
    tmp_path: Path,
    evidence_type: str,
) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    bundle = get_bundle(service, request)
    bundle.evidence_records = [
        bundle.evidence_records[0].model_copy(update={"evidence_type": evidence_type})
    ]

    service.ledger_service.get_spend_authorization_bundle = (  # type: ignore[method-assign]
        lambda spend_request_id: bundle if spend_request_id == request.spend_request_id else None
    )
    result = service.capped_send(request)
    backend = service.backend
    assert isinstance(backend, FakeWalletBackend)
    events = service.ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
    )

    assert result.status == "rejected"
    assert result.reason == "evidence_type_not_allowed"
    assert backend.state.send_count == 0
    assert any(
        isinstance(event.payload.get("payload"), dict)
        and event.payload.get("related_record_id") == "spend_001"
        and cast(dict[str, object], event.payload["payload"]).get("event_name")
        == "wallet_send_rejected"
        and cast(dict[str, object], event.payload["payload"]).get("reason_code")
        == "evidence_type_not_allowed"
        for event in events
    )


@pytest.mark.parametrize(
    "evidence_type",
    ["terms_snapshot", "receipt", "invoice", "payment_request"],
)
def test_send_accepts_allowed_spend_evidence_types(tmp_path: Path, evidence_type: str) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    bundle = get_bundle(service, request)
    bundle.evidence_records = [
        bundle.evidence_records[0].model_copy(update={"evidence_type": evidence_type})
    ]

    service.ledger_service.get_spend_authorization_bundle = (  # type: ignore[method-assign]
        lambda spend_request_id: bundle if spend_request_id == request.spend_request_id else None
    )
    result = service.capped_send(request)

    assert result.status == "sent"


def test_balance_failure_returns_error_and_writes_audit_event(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    quote_called = False

    def raise_balance_error() -> int:
        raise WalletBackendError("boom")

    def mark_quote(request: WalletQuoteRequest) -> WalletQuoteResponse:
        nonlocal quote_called
        quote_called = True
        return WalletGovernorService.quote(service, request)

    service.backend.get_balance_sats = raise_balance_error  # type: ignore[method-assign]
    service.quote = mark_quote  # type: ignore[method-assign]
    result = service.capped_send(request)
    backend = service.backend
    assert isinstance(backend, FakeWalletBackend)
    events = service.ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
    )

    assert result.status == "error"
    assert result.reason == "backend_error"
    assert quote_called is False
    assert backend.state.last_unlock_seconds == 0
    assert backend.state.send_count == 0
    assert service.ledger_service.list_wallet_transactions_for_spend_request("spend_001") == []
    assert any(
        isinstance(event.payload.get("payload"), dict)
        and event.payload.get("related_record_id") == "spend_001"
        and cast(dict[str, object], event.payload["payload"]).get("event_name")
        == "wallet_backend_balance_failed"
        and cast(dict[str, object], event.payload["payload"]).get("reason_code")
        == "backend_error"
        for event in events
    )


def test_send_rejects_over_single_limit(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    result = service.capped_send(seed_spend_request(service, amount_usd=50.0))

    assert result.status == "rejected"
    assert result.reason == "budget_amount_exceeded"


def test_send_requires_references() -> None:
    try:
        make_request(ledger_record_id="")
    except ValidationError as error:
        assert "ledger_record_id" in str(error)
    else:
        raise AssertionError("Expected missing ledger reference validation failure")


def test_duplicate_idempotency_returns_same_response(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)

    first = service.capped_send(request)
    second = service.capped_send(request)

    assert first.txid == second.txid
    assert second.status == "sent"


def test_conflicting_idempotent_retry_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)

    first = service.capped_send(request)
    conflicting = request.model_copy(update={"amount_usd": 4.5})
    second = service.capped_send(conflicting)

    assert first.status == "sent"
    assert second.status == "rejected"
    assert second.reason == "idempotency_conflict"


def test_successful_send_records_ledger_and_locks_wallet(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)

    result = service.capped_send(request)

    assert result.status == "sent"
    assert result.spend_request_id is not None
    assert result.wallet_transaction_id is not None
    backend = service.backend
    assert isinstance(backend, FakeWalletBackend)
    assert backend.state.lock_count == 1
    assert backend.state.send_count == 1


def test_send_rejects_unsupported_asset(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service, asset="ETH")

    result = service.capped_send(request)

    assert result.status == "rejected"
    assert result.reason == "unsupported_asset"


def test_send_rejects_when_prior_wallet_transaction_exists(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    service.ledger_service.record_wallet_transaction(
        WalletTransactionRecord(
            created_at=utc_now(),
            wallet_transaction_id="wallet_tx_existing",
            spend_request_id=request.spend_request_id or "",
            txid="tx_existing",
            amount_btc="0.00010000",
            fee_btc="0.00000250",
            amount_usd_estimate=5.0,
            fee_usd_estimate=0.13,
            total_usd_estimate=5.13,
            status=WalletTransactionStatus.SENT,
            destination=request.destination,
            purpose=request.purpose,
        ),
        idempotency_key="wallet:tx:existing",
    )

    result = service.capped_send(request)

    assert result.status == "rejected"
    assert result.reason == "spend_request_status_invalid"


def test_send_rejects_ineligible_spend_request_status(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    service.ledger_service.update_spend_request_status(
        request.spend_request_id or "",
        SpendRequestStatus.SENT.value,
        idempotency_key="wallet:spend-status:terminal",
    )

    result = service.capped_send(request)

    assert result.status == "rejected"
    assert result.reason == "spend_request_status_invalid"


def test_send_rejects_missing_ledger_prewrite_context(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_without_prewrite(service)

    result = service.capped_send(request)

    assert result.status == "rejected"
    assert result.reason == "spend_request_missing"


def test_send_rejects_bundle_validation_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(tmp_path)

    def case(
        *,
        label: str,
        mutate: Mutator,
        expected_reason: str,
        seed_kwargs: dict[str, object] | None = None,
    ) -> tuple[str, Mutator, str, dict[str, object] | None]:
        return label, mutate, expected_reason, seed_kwargs

    cases = [
        case(
            label="mismatched-ledger-record",
            mutate=lambda request, bundle, svc: setattr(
                request,
                "ledger_record_id",
                "other-ledger",
            ),
            expected_reason="ledger_record_mismatch",
        ),
        case(
            label="mismatched-opportunity",
            mutate=lambda request, bundle, svc: setattr(request, "opportunity_id", "opp_other"),
            expected_reason="opportunity_id_mismatch",
        ),
        case(
            label="mismatched-counterparty",
            mutate=lambda request, bundle, svc: setattr(request, "counterparty", "Other Vendor"),
            expected_reason="counterparty_mismatch",
        ),
        case(
            label="mismatched-purpose",
            mutate=lambda request, bundle, svc: setattr(request, "purpose", "Other purpose"),
            expected_reason="purpose_mismatch",
        ),
        case(
            label="policy-missing",
            mutate=lambda request, bundle, svc: setattr(bundle, "policy_decision", None),
            expected_reason="policy_missing",
        ),
        case(
            label="policy-not-allow",
            mutate=update_policy(decision=PolicyDecisionType.BLOCK),
            expected_reason="policy_not_allow",
        ),
        case(
            label="policy-opportunity-mismatch",
            mutate=update_policy(opportunity_id="opp_else"),
            expected_reason="policy_context_mismatch",
        ),
        case(
            label="budget-missing",
            mutate=lambda request, bundle, svc: setattr(bundle, "budget_plan", None),
            expected_reason="budget_missing",
        ),
        case(
            label="budget-non-executable",
            mutate=update_budget(decision=BudgetDecisionType.REJECT),
            expected_reason="budget_not_executable",
        ),
        case(
            label="budget-wallet-spend-disabled",
            mutate=update_budget(wallet_spend_request_allowed=False),
            expected_reason="budget_wallet_spend_not_allowed",
        ),
        case(
            label="budget-opportunity-mismatch",
            mutate=update_budget(opportunity_id="opp_else"),
            expected_reason="budget_not_executable",
        ),
        case(
            label="blank-success-metric",
            mutate=update_budget(success_metric="  "),
            expected_reason="budget_not_executable",
        ),
        case(
            label="blank-stop-condition",
            mutate=update_budget(stop_condition="  "),
            expected_reason="budget_not_executable",
        ),
        case(
            label="approved-categories-exclude-request",
            mutate=update_budget(approved_spend_categories=["hosting"]),
            expected_reason="budget_wallet_spend_not_allowed",
        ),
        case(
            label="tos-missing",
            mutate=lambda request, bundle, svc: setattr(bundle, "tos_legal_check", None),
            expected_reason="tos_missing",
        ),
        case(
            label="tos-opportunity-mismatch",
            mutate=update_tos(opportunity_id="opp_else"),
            expected_reason="tos_not_proceed",
        ),
        case(
            label="tos-no-evidence-ids",
            mutate=update_tos(evidence_archive_ids=[]),
            expected_reason="evidence_missing",
        ),
        case(
            label="blank-category",
            mutate=sync_category_everywhere(""),
            expected_reason="category_missing",
        ),
        case(
            label="built-in-blocked-category",
            mutate=sync_category_everywhere("gambling"),
            expected_reason="category_blocked",
        ),
        case(
            label="policy-config-blocked-category",
            mutate=block_policy_category("custom_blocked"),
            expected_reason="category_blocked",
        ),
        case(
            label="unknown-category",
            mutate=sync_category_everywhere("mystery"),
            expected_reason="category_unknown",
        ),
        case(
            label="spend-request-no-evidence",
            mutate=lambda request, bundle, svc: setattr(
                bundle,
                "spend_request",
                bundle.spend_request.model_copy(update={"evidence_archive_ids": []}),
            ),
            expected_reason="evidence_ids_mismatch",
        ),
        case(
            label="unrelated-evidence",
            mutate=set_unrelated_evidence,
            expected_reason="evidence_unrelated",
        ),
        case(
            label="blank-destination",
            mutate=sync_request_and_spend_request("destination", ""),
            expected_reason="destination_missing",
        ),
        case(
            label="placeholder-destination",
            mutate=sync_request_and_spend_request("destination", "placeholder-wallet"),
            expected_reason="destination_invalid",
        ),
        case(
            label="send-all-destination",
            mutate=sync_request_and_spend_request("destination", "send all wallet"),
            expected_reason="send_all_blocked",
        ),
        case(
            label="send-all-purpose",
            mutate=sync_request_and_spend_request("purpose", "send all funds now"),
            expected_reason="send_all_blocked",
        ),
        case(
            label="invalid-btc-destination",
            mutate=sync_request_and_spend_request("destination", "invalid-address"),
            expected_reason="destination_invalid",
        ),
        case(
            label="missing-ledger-record-context",
            mutate=lambda request, bundle, svc: setattr(bundle, "ledger_record_exists", False),
            expected_reason="spend_request_missing",
        ),
    ]

    for label, mutate, expected_reason, seed_kwargs in cases:
        request = seed_spend_request(
            service,
            spend_request_id=f"spend_{label.replace('-', '_')}",
            idempotency_key=f"send_{label.replace('-', '_')}",
            **(seed_kwargs or {}),
        )
        assert_reason_for_mutated_bundle(
            service,
            request,
            monkeypatch,
            mutate=mutate,
            expected_reason=expected_reason,
        )
        monkeypatch.undo()


def test_limit_helpers_cover_single_daily_and_weekly_rejections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(tmp_path)

    assert service._limit_rejection_code(50.0) == "amount_exceeds_single_limit"

    monkeypatch.setattr(
        service.ledger_service,
        "get_remaining_daily_limit",
        lambda day, limit: 4.0,
    )
    monkeypatch.setattr(
        service.ledger_service,
        "get_remaining_weekly_limit",
        lambda day, limit: 100.0,
    )
    assert service._limit_rejection_code(5.0) == "amount_exceeds_daily_limit"

    monkeypatch.setattr(
        service.ledger_service,
        "get_remaining_daily_limit",
        lambda day, limit: 100.0,
    )
    monkeypatch.setattr(
        service.ledger_service,
        "get_remaining_weekly_limit",
        lambda day, limit: 4.0,
    )
    assert service._limit_rejection_code(5.0) == "amount_exceeds_weekly_limit"


def test_asset_and_destination_helpers_cover_edge_cases(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(ValueError):
        service._require_supported_asset("ETH")

    assert service._validate_destination("USD", " account-123 ").is_valid is True
    assert service._validate_destination("USD", "   ").is_valid is False


def test_quote_json_and_capped_send_json_reject_malformed_payloads(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(ValidationError):
        service.quote_json({"asset": "BTC", "amount_usd": 0.0, "btc_usd_rate": 50_000.0})

    with pytest.raises(ValidationError):
        service.capped_send_json({"asset": "BTC", "amount_usd": 5.0})


def test_store_rejection_can_skip_cache_mutation(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    cached = service.capped_send(request)

    response = service._store_rejection(
        request.model_copy(update={"idempotency_key": "send_no_cache"}),
        "policy_missing",
        cache_response=False,
    )

    assert response.reason == "policy_missing"
    assert service._responses[request.idempotency_key] == cached
    assert "send_no_cache" not in service._responses


def test_store_rejection_only_updates_status_for_eligible_bundles(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    eligible_request = seed_spend_request(
        service,
        spend_request_id="spend_eligible",
        idempotency_key="send_eligible",
    )
    eligible_bundle = get_bundle(service, eligible_request)
    service._store_rejection(eligible_request, "policy_missing", bundle=eligible_bundle)
    eligible_spend = service.ledger_service.get_spend_request("spend_eligible")
    assert eligible_spend is not None
    assert eligible_spend.status == SpendRequestStatus.REJECTED

    terminal_request = seed_spend_request(
        service,
        spend_request_id="spend_terminal",
        idempotency_key="send_terminal",
    )
    service.ledger_service.update_spend_request_status(
        "spend_terminal",
        SpendRequestStatus.SENT.value,
        idempotency_key="wallet:spend-status:sent:terminal",
    )
    terminal_bundle = get_bundle(service, terminal_request)
    service._store_rejection(terminal_request, "policy_missing", bundle=terminal_bundle)
    terminal_spend = service.ledger_service.get_spend_request("spend_terminal")
    assert terminal_spend is not None
    assert terminal_spend.status == SpendRequestStatus.SENT


def test_send_rejects_send_all_request() -> None:
    try:
        make_request(send_all=True)
    except ValidationError as error:
        assert "send_all" in str(error)
    else:
        raise AssertionError("Expected send_all validation failure")


def test_send_rejects_missing_evidence_file(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    bundle = get_bundle(service, request)
    assert bundle.evidence_records
    Path(bundle.evidence_records[0].archive_path).unlink()

    result = service.capped_send(request)

    assert result.status == "rejected"
    assert result.reason == "evidence_missing"


def test_send_rejects_evidence_hash_mismatch(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    bundle = get_bundle(service, request)
    assert bundle.evidence_records
    Path(bundle.evidence_records[0].archive_path).write_text("tampered", encoding="utf-8")

    result = service.capped_send(request)

    assert result.status == "rejected"
    assert result.reason == "evidence_hash_mismatch"


def test_send_rejects_evidence_path_outside_archive_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    bundle = get_bundle(service, request)
    assert bundle.evidence_records
    bundle.evidence_records[0] = bundle.evidence_records[0].model_copy(
        update={"archive_path": str(tmp_path.parent / "escape.txt")}
    )
    monkeypatch.setattr(
        service.ledger_service,
        "get_spend_authorization_bundle",
        lambda spend_request_id: bundle if spend_request_id == request.spend_request_id else None,
    )

    result = service.capped_send(request)

    assert result.status == "rejected"
    assert result.reason == "evidence_path_invalid"


def test_quote_fee_failure_returns_structured_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(tmp_path)

    def raise_fee_error(amount_sats: int) -> int:
        del amount_sats
        raise WalletBackendError("fee unavailable")

    monkeypatch.setattr(service.backend, "estimate_fee_sats", raise_fee_error)

    result = service.quote(
        WalletQuoteRequest(
            asset="BTC",
            amount_usd=5.0,
            btc_usd_rate=50_000.0,
            destination="bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "fee_quote_failed"


def test_unlock_failure_returns_error_without_sending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(
        service,
        spend_request_id="spend_unlock",
        idempotency_key="send_unlock",
    )

    def raise_unlock_error(seconds: int) -> None:
        del seconds
        raise WalletBackendError("unlock failed")

    monkeypatch.setattr(service.backend, "unlock", raise_unlock_error)

    result = service.capped_send(request)

    backend = service.backend
    assert isinstance(backend, FakeWalletBackend)
    assert result.status == "error"
    assert result.reason == "wallet_unlock_failed"
    assert backend.state.send_count == 0
    spend_request = service.ledger_service.get_spend_request("spend_unlock")
    assert spend_request is not None
    assert spend_request.status == SpendRequestStatus.FAILED


def test_send_failure_returns_error_and_no_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(
        service,
        spend_request_id="spend_send_fail",
        idempotency_key="send_send_fail",
    )

    def raise_send_error(destination: str, amount_sats: int) -> str:
        del destination, amount_sats
        raise WalletBackendError("send failed")

    monkeypatch.setattr(service.backend, "send_to_address", raise_send_error)

    result = service.capped_send(request)

    backend = service.backend
    assert isinstance(backend, FakeWalletBackend)
    assert result.status == "error"
    assert result.reason == "wallet_send_failed"
    assert backend.state.lock_count == 1
    assert (
        service.ledger_service.list_wallet_transactions_for_spend_request(
            "spend_send_fail"
        )
        == []
    )


def test_lock_failure_returns_warning_after_successful_send(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(
        service,
        spend_request_id="spend_lock_fail",
        idempotency_key="send_lock_fail",
    )

    def raise_lock_error() -> None:
        raise WalletBackendError("lock failed")

    monkeypatch.setattr(service.backend, "lock", raise_lock_error)

    result = service.capped_send(request)
    audit_events = service.ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
    )

    assert result.status == "sent"
    assert result.warnings == ["wallet_lock_failed"]
    assert any(
        isinstance(payload, dict)
        and payload.get("event_name") == "wallet_lock_failed"
        and event.payload.get("related_record_id") == "spend_lock_fail"
        for event in audit_events
        for payload in [event.payload.get("payload")]
    )
