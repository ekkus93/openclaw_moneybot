"""Tests for the wallet governor HTTP wrapper."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from openclaw_moneybot.plugins.wallet_governor_service import (
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletGovernorService,
    create_wallet_governor_app,
)
from openclaw_moneybot.plugins.wallet_governor_service.backend import WalletBackendError
from openclaw_moneybot.shared import (
    BudgetPlan,
    EvidenceRecord,
    LedgerRecord,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    TosLegalCheck,
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
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver.hashing import sha256_bytes
from openclaw_moneybot.skills.wallet_governor_client.models import WalletSpendRequest
from openclaw_moneybot.utils.time import utc_now


def make_service(tmp_path: Path, *, spend_enabled: bool = True) -> WalletGovernorService:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_root = tmp_path / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    evidence_path = archive_root / "artifact_001.html"
    evidence_bytes = b"http wallet test evidence"
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


def seed_spend_request(service: WalletGovernorService) -> WalletSpendRequest:
    prewrite = service.ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=utc_now(),
            record_id="audit_prewrite_http_001",
            record_type=RecordType.AUDIT_EVENT,
            related_record_id="spend_001",
            payload={"event_name": "wallet_prewrite"},
        ),
        idempotency_key="prewrite:http:spend_001",
    )
    service.ledger_service.record_spend_request(
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
            purpose="Pay a small approved invoice",
            category="purchase",
            evidence_archive_ids=["artifact_001"],
            status="proposed",
        ),
        idempotency_key="spend:http:001",
    )
    return WalletSpendRequest.model_validate(
        {
            "spend_request_id": "spend_001",
            "opportunity_id": "opp_001",
            "policy_decision_id": "policy_001",
            "budget_plan_id": "budget_001",
            "tos_legal_check_id": "tos_001",
            "ledger_event_id": prewrite.ledger_event_id,
            "amount_usd": 5.0,
            "asset": "BTC",
            "destination": "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
            "counterparty": "Example Vendor",
            "purpose": "Pay a small approved invoice",
            "category": "purchase",
            "evidence_archive_ids": ["artifact_001"],
            "btc_usd_rate": 50_000.0,
            "idempotency_key": "client_send_http_001",
        }
    )


def service_payload(request: WalletSpendRequest) -> dict[str, object]:
    payload = request.model_dump(mode="json")
    payload.pop("tos_legal_check_id", None)
    payload.pop("source_url", None)
    payload.pop("receipt_expected", None)
    payload["ledger_record_id"] = payload.pop("ledger_event_id")
    return payload


def make_client(tmp_path: Path, *, spend_enabled: bool = True) -> TestClient:
    service = make_service(tmp_path, spend_enabled=spend_enabled)
    app = create_wallet_governor_app(service)
    return TestClient(app)


def test_health_endpoint_reports_service_metadata(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["backend_mode"] == "fake"


def test_balance_endpoint_returns_local_state(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/balance", params={"asset": "BTC"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset"] == "BTC"
    assert payload["spend_enabled"] is True
    assert payload["network"] == "local"


def test_limits_endpoint_returns_categories(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/limits", params={"asset": "BTC"})

    assert response.status_code == 200
    payload = response.json()
    assert "allowed_categories" in payload
    assert "blocked_categories" in payload


def test_quote_endpoint_returns_fee_estimates(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/quote-spend",
            json={
                "asset": "BTC",
                "amount_usd": 5.0,
                "btc_usd_rate": 50_000.0,
                "destination": "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fee_btc"] != "0"
    assert payload["estimated_fee_usd"] > 0
    assert payload["total_usd_estimate"] > payload["amount_usd"]


def test_quote_endpoint_rejects_invalid_destination(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/quote-spend",
            json={
                "asset": "BTC",
                "amount_usd": 5.0,
                "btc_usd_rate": 50_000.0,
                "destination": "invalid-address",
            },
        )

    assert response.status_code == 200
    assert response.json()["reason"] == "destination_invalid"


def test_quote_endpoint_rejects_blocklisted_destination(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.config.blocked_destinations = ["bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2"]
    with TestClient(create_wallet_governor_app(service)) as client:
        response = client.post(
            "/quote-spend",
            json={
                "asset": "BTC",
                "amount_usd": 5.0,
                "btc_usd_rate": 50_000.0,
                "destination": "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
            },
        )

    assert response.status_code == 200
    assert response.json()["reason"] == "destination_blocked"


def test_send_endpoint_rejects_when_spend_disabled(tmp_path: Path) -> None:
    service = make_service(tmp_path, spend_enabled=False)
    request = seed_spend_request(service)
    with TestClient(create_wallet_governor_app(service)) as client:
        response = client.post("/send-small-payment", json=service_payload(request))

    assert response.status_code == 200
    assert response.json()["reason"] == "spend_disabled"


def test_send_endpoint_succeeds_with_valid_prewrite(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    request = seed_spend_request(service)
    with TestClient(create_wallet_governor_app(service)) as client:
        response = client.post("/send-small-payment", json=service_payload(request))

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "sent"
    assert payload["txid"]


def test_http_wrapper_rejects_non_local_bind() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(Path(tmp))
        try:
            create_wallet_governor_app(service, bind_host="0.0.0.0")
        except ValueError as error:
            assert "localhost" in str(error)
        else:
            raise AssertionError("Expected non-local bind host to be rejected")


def test_health_endpoint_includes_version(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    with TestClient(create_wallet_governor_app(service, service_version="9.9.9")) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["version"] == "9.9.9"


def test_timeout_middleware_returns_http_504(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    service = make_service(tmp_path)

    def slow_quote(payload: dict[str, object]) -> dict[str, object]:
        del payload
        time.sleep(0.05)
        return {"status": "ok"}

    monkeypatch.setattr(service, "quote_json", slow_quote)
    with TestClient(
        create_wallet_governor_app(service, request_timeout_seconds=0.01)
    ) as client:
        response = client.post(
            "/quote-spend",
            json={
                "asset": "BTC",
                "amount_usd": 5.0,
                "btc_usd_rate": 50_000.0,
                "destination": "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
            },
        )

    assert response.status_code == 504
    assert response.json() == {"detail": "request timed out"}


def test_value_error_handler_returns_http_400(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    service = make_service(tmp_path)

    def raise_value_error(payload: dict[str, object]) -> dict[str, object]:
        del payload
        raise ValueError("bad request")

    monkeypatch.setattr(service, "quote_json", raise_value_error)
    with TestClient(create_wallet_governor_app(service)) as client:
        response = client.post("/quote-spend", json={})

    assert response.status_code == 400
    assert response.json() == {"detail": "bad request"}


def test_backend_error_handler_returns_http_502(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    service = make_service(tmp_path)

    def raise_backend_error(asset: str) -> object:
        del asset
        raise WalletBackendError("backend unavailable")

    monkeypatch.setattr(service, "balance", raise_backend_error)
    with TestClient(create_wallet_governor_app(service)) as client:
        response = client.get("/balance", params={"asset": "BTC"})

    assert response.status_code == 502
    assert response.json() == {"detail": "backend unavailable"}


def test_validation_error_handler_returns_http_422(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post("/quote-spend", json={"asset": "BTC"})

    assert response.status_code == 422
    assert response.json()["detail"]
