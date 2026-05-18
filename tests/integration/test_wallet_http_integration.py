"""Integration tests for wallet client and local HTTP wrapper."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import JsonValue
from pytest import MonkeyPatch

from openclaw_moneybot.plugins.wallet_governor_service.backend import WalletBackendError
from openclaw_moneybot.plugins.wallet_governor_service.http import create_wallet_governor_app
from openclaw_moneybot.plugins.wallet_governor_service.service import WalletGovernorService
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.wallet_governor_client import (
    WalletBalanceRequest,
    WalletGovernorClientSkill,
    WalletQuoteSkillRequest,
    WalletSpendRequest,
)
from openclaw_moneybot.skills.wallet_governor_client.client import (
    WalletGovernorClientError,
    WalletGovernorHttpClient,
)

from .helpers import (
    make_archive_config,
    make_prewrite_record,
    make_wallet_client_skill,
    make_wallet_service,
    make_wallet_test_client,
    seed_budget_plan,
    seed_evidence_record,
    seed_opportunity,
    seed_policy_decision,
    seed_tos_legal_check,
)


def make_wallet_stack(
    tmp_path: Path,
    *,
    spend_enabled: bool,
    timeout_seconds: float = 10.0,
) -> tuple[LedgerService, WalletGovernorService, TestClient, WalletGovernorClientSkill]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    seed_opportunity(ledger_service)
    seed_policy_decision(ledger_service)
    seed_tos_legal_check(ledger_service)
    seed_budget_plan(ledger_service)
    seed_evidence_record(ledger_service)
    archive_config = make_archive_config(tmp_path)
    service = make_wallet_service(
        ledger_service,
        spend_enabled=spend_enabled,
        timeout_seconds=timeout_seconds,
    )
    client = make_wallet_test_client(service, request_timeout_seconds=timeout_seconds)
    skill = make_wallet_client_skill(
        ledger_service,
        archive_config,
        spend_enabled=spend_enabled,
        transport=client._transport,
        timeout_seconds=timeout_seconds,
    )
    return ledger_service, service, client, skill


def make_spend_request(ledger_service: LedgerService, **overrides: object) -> WalletSpendRequest:
    payload: dict[str, object] = {
        "spend_request_id": "spend_001",
        "opportunity_id": "opp_001",
        "policy_decision_id": "policy_001",
        "budget_plan_id": "budget_001",
        "tos_legal_check_id": "tos_001",
        "ledger_event_id": make_prewrite_record(ledger_service, related_id="spend_001"),
        "amount_usd": 5.0,
        "asset": "BTC",
        "destination": "bcrt1qmoneybotdest123",
        "counterparty": "Example Vendor",
        "purpose": "Approved small payment",
        "category": "purchase",
        "evidence_archive_ids": ["artifact_001"],
        "btc_usd_rate": 50_000.0,
        "idempotency_key": "wallet-client-send-001",
    }
    payload.update(overrides)
    return WalletSpendRequest.model_validate(payload)


def make_service_payload(request: WalletSpendRequest) -> dict[str, JsonValue]:
    return {
        "spend_request_id": request.spend_request_id,
        "opportunity_id": request.opportunity_id,
        "budget_plan_id": request.budget_plan_id,
        "policy_decision_id": request.policy_decision_id,
        "ledger_record_id": request.ledger_event_id,
        "amount_usd": request.amount_usd,
        "asset": request.asset,
        "destination": request.destination,
        "counterparty": request.counterparty,
        "purpose": request.purpose,
        "category": request.category,
        "btc_usd_rate": request.btc_usd_rate,
        "send_all": False,
        "evidence_archive_ids": [item for item in request.evidence_archive_ids],
        "idempotency_key": request.idempotency_key,
    }


def test_wallet_client_get_balance_uses_real_http_wrapper(tmp_path: Path) -> None:
    _, _, client, skill = make_wallet_stack(tmp_path, spend_enabled=True)
    with client:
        result = skill.get_balance(WalletBalanceRequest(asset="BTC", btc_usd_rate=50_000.0))

    assert result.asset == "BTC"
    assert result.usd_estimate == 2500.0
    assert result.service_limits["asset"] == "BTC"


def test_wallet_client_quote_uses_real_http_wrapper(tmp_path: Path) -> None:
    _, _, client, skill = make_wallet_stack(tmp_path, spend_enabled=True)
    with client:
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
    assert result.raw_response["total_usd_estimate"] == pytest.approx(5.13)


def test_wallet_client_spend_succeeds_through_real_http_wrapper(tmp_path: Path) -> None:
    ledger_service, _, client, skill = make_wallet_stack(tmp_path, spend_enabled=True)
    with client:
        result = skill.spend(make_spend_request(ledger_service))

    assert result.status == "sent"
    assert result.wallet_transaction_id is not None
    assert result.raw_response_evidence_id is not None
    assert ledger_service.get_wallet_transaction(result.wallet_transaction_id) is not None


def test_wallet_client_spend_rejected_through_real_http_wrapper_when_disabled(
    tmp_path: Path,
) -> None:
    ledger_service, _, client, skill = make_wallet_stack(tmp_path, spend_enabled=False)
    with client:
        result = skill.spend(make_spend_request(ledger_service))

    assert result.status == "rejected"
    assert "spend disabled" in result.rejection_reasons
    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)
    assert any(
        event.payload.get("related_record_id") == result.spend_request_id for event in audit_events
    )


def test_wallet_client_preserves_service_side_validation_rejection_reason(
    tmp_path: Path,
) -> None:
    ledger_service, service, client, skill = make_wallet_stack(tmp_path, spend_enabled=True)
    service.config.allowed_assets = ["ETH"]

    with client:
        result = skill.spend(make_spend_request(ledger_service))

    assert result.status == "rejected"
    assert "unsupported_asset" in result.rejection_reasons
    assert result.raw_response_evidence_id is not None


def test_wallet_http_client_reports_safe_error_for_malformed_request(
    tmp_path: Path,
) -> None:
    _, _, client, _ = make_wallet_stack(tmp_path, spend_enabled=True)
    http_client = WalletGovernorHttpClient(
        make_wallet_service(
            LedgerService.from_db_path(tmp_path / "extra.sqlite3"),
            spend_enabled=True,
        ).config,
        transport=client._transport,
    )

    with client:
        with pytest.raises(WalletGovernorClientError, match="request failed"):
            http_client.send_small_payment({"bad": "payload"})

    http_client.close()


def test_wallet_client_surfaces_backend_failure_through_http_wrapper(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    ledger_service, service, client, skill = make_wallet_stack(tmp_path, spend_enabled=True)

    def raise_backend_error(destination: str, amount_sats: int) -> str:
        del amount_sats, destination
        raise WalletBackendError("backend unavailable")

    monkeypatch.setattr(service.backend, "send_to_address", raise_backend_error)
    with client:
        result = skill.spend(make_spend_request(ledger_service))

    assert result.status == "error"
    assert "wallet governor returned an error" in result.rejection_reasons
    assert result.raw_response_evidence_id is not None


def test_wallet_client_surfaces_timeout_through_http_wrapper(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    ledger_service, service, client, skill = make_wallet_stack(
        tmp_path,
        spend_enabled=True,
        timeout_seconds=0.01,
    )

    def slow_capped_send_json(payload: dict[str, object]) -> dict[str, object]:
        del payload
        time.sleep(0.05)
        return {"status": "sent"}

    monkeypatch.setattr(service, "capped_send_json", slow_capped_send_json)
    with client:
        result = skill.spend(
            make_spend_request(
                ledger_service,
                spend_request_id="spend_timeout",
                idempotency_key="wallet-client-send-timeout",
            )
        )

    assert result.status == "error"
    assert "wallet governor request failed" in result.rejection_reasons[0]
    assert result.raw_response_evidence_id is not None


def test_wallet_send_replay_through_http_wrapper_does_not_duplicate_transaction(
    tmp_path: Path,
) -> None:
    ledger_service, _, client, skill = make_wallet_stack(tmp_path, spend_enabled=True)
    request = make_spend_request(
        ledger_service,
        spend_request_id="spend_replay",
        idempotency_key="wallet-client-send-replay",
    )

    with client:
        first_result = skill.spend(request)
        second_result = skill.spend(request)

    wallet_transactions = ledger_service.list_wallet_transactions_for_opportunity("opp_001")

    assert first_result.status == "sent"
    assert second_result.status == "sent"
    assert first_result.wallet_transaction_id == second_result.wallet_transaction_id
    assert len(wallet_transactions) == 1


def test_wallet_http_wrapper_rejects_idempotency_conflict_payload(tmp_path: Path) -> None:
    ledger_service, service, client, skill = make_wallet_stack(tmp_path, spend_enabled=True)
    http_client = WalletGovernorHttpClient(service.config, transport=client._transport)
    request = make_spend_request(
        ledger_service,
        spend_request_id="spend_conflict",
        idempotency_key="wallet-conflict",
    )
    first_payload = make_service_payload(request)
    conflicting_payload = dict(first_payload)
    conflicting_payload["amount_usd"] = 6.0

    with client:
        first_result = skill.spend(request)
        conflict_response = http_client.send_small_payment(conflicting_payload)

    http_client.close()

    assert first_result.status == "sent"
    assert conflict_response["status"] == "rejected"
    assert conflict_response["reason"] == "idempotency_conflict"
    assert len(ledger_service.list_wallet_transactions_for_opportunity("opp_001")) == 1


def test_wallet_http_app_rejects_non_local_bind_host(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    service = make_wallet_service(ledger_service, spend_enabled=True)

    with pytest.raises(ValueError, match="must bind to localhost or 127.0.0.1"):
        create_wallet_governor_app(service, bind_host="0.0.0.0")


def test_wallet_http_client_health_works_against_local_in_process_boundary(
    tmp_path: Path,
) -> None:
    _, service, client, _ = make_wallet_stack(tmp_path, spend_enabled=True)
    http_client = WalletGovernorHttpClient(service.config, transport=client._transport)

    with client:
        health = http_client.health()

    http_client.close()

    assert health["status"] == "ok"
    assert health["backend_mode"] == "fake"
