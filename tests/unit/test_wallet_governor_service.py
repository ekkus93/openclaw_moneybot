"""Tests for the wallet governor service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from openclaw_moneybot.plugins.wallet_governor_service import (
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletGovernorService,
    WalletQuoteRequest,
    WalletSendRequest,
)
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
    BudgetDecisionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RecordType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.ledger_skill.models import SpendAuthorizationBundle
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.utils.time import utc_now

Mutator = Callable[
    [WalletSendRequest, SpendAuthorizationBundle, WalletGovernorService],
    None,
]


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
    ledger_service.record_evidence(
        EvidenceRecord(
            created_at=datetime(2026, 1, 1, 0, 4, tzinfo=UTC),
            evidence_id="artifact_001",
            related_record_type=RecordType.OPPORTUNITY,
            related_record_id="opp_001",
            evidence_type="html_snapshot",
            archive_path="archive/2026/01/01/artifact_001.html",
            content_sha256="a" * 64,
            source_url="https://example.com/opportunity",
        ),
        idempotency_key="evidence:artifact_001",
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
        "spend_request_id": "spend_001",
        "opportunity_id": "opp_001",
        "budget_plan_id": "budget_001",
        "policy_decision_id": "policy_001",
        "ledger_record_id": "ledger_001",
        "amount_usd": 5.0,
        "asset": "BTC",
        "destination": "bcrt1qmoneybotdest123",
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
        sync_request_and_spend_request("category", value)(request, bundle, service)

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
    del request, service
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
            destination="bcrt1qmoneybotdest123",
        )
    )

    assert result.amount_sats > 0
    assert result.fee_sats > 0


def test_send_rejects_when_spend_disabled(tmp_path: Path) -> None:
    service = make_service(tmp_path, spend_enabled=False)

    result = service.capped_send(seed_spend_request(service))

    assert result.status == "rejected"
    assert result.reason == "spend_disabled"


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
            expected_reason="spend_request_mismatch",
        ),
        case(
            label="mismatched-opportunity",
            mutate=lambda request, bundle, svc: setattr(request, "opportunity_id", "opp_other"),
            expected_reason="spend_request_mismatch",
        ),
        case(
            label="mismatched-counterparty",
            mutate=lambda request, bundle, svc: setattr(request, "counterparty", "Other Vendor"),
            expected_reason="spend_request_mismatch",
        ),
        case(
            label="mismatched-purpose",
            mutate=lambda request, bundle, svc: setattr(request, "purpose", "Other purpose"),
            expected_reason="spend_request_mismatch",
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
            expected_reason="policy_not_allow",
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
            mutate=sync_request_and_spend_request("category", ""),
            expected_reason="category_missing",
        ),
        case(
            label="built-in-blocked-category",
            mutate=sync_request_and_spend_request("category", "gambling"),
            expected_reason="category_blocked",
        ),
        case(
            label="policy-config-blocked-category",
            mutate=block_policy_category("custom_blocked"),
            expected_reason="category_blocked",
        ),
        case(
            label="unknown-category",
            mutate=sync_request_and_spend_request("category", "mystery"),
            expected_reason="category_unknown",
        ),
        case(
            label="spend-request-no-evidence",
            mutate=lambda request, bundle, svc: setattr(
                bundle,
                "spend_request",
                bundle.spend_request.model_copy(update={"evidence_archive_ids": []}),
            ),
            expected_reason="evidence_missing",
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

    assert service._validate_destination("USD", " account-123 ")
    assert not service._validate_destination("USD", "   ")


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
