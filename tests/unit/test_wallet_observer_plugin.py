"""Unit tests for the read-only wallet observer plugin."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from openclaw_moneybot.plugins.wallet_governor_service.backend import (
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletBackendError,
)
from openclaw_moneybot.plugins.wallet_observer_plugin import (
    WalletBalanceObservationRequest,
    WalletObserverPlugin,
    WalletTransactionObservationRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, WalletObserverConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


class RichFakeWalletBackend(FakeWalletBackend):
    def __init__(
        self,
        state: FakeWalletBackendState,
        *,
        transaction_payload: dict[str, object] | None = None,
        fail_lookup: bool = False,
    ) -> None:
        super().__init__(state)
        self.transaction_payload = transaction_payload or {"confirmations": 1}
        self.fail_lookup = fail_lookup

    def get_transaction(self, txid: str) -> dict[str, object]:
        if self.fail_lookup:
            raise WalletBackendError("lookup failed")
        return {"txid": txid, **self.transaction_payload}


def make_plugin(
    tmp_path: Path,
    *,
    backend: RichFakeWalletBackend | None = None,
    read_only: bool = True,
) -> tuple[WalletObserverPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = WalletObserverPlugin(
        WalletObserverConfig(enabled=True, read_only=read_only),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        backend or RichFakeWalletBackend(FakeWalletBackendState(balance_sats=500_000)),
    )
    return plugin, ledger_service


def test_read_only_balance_fetch_succeeds(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    result = plugin.observe_balance(WalletBalanceObservationRequest())

    assert result.balance_sats == 500_000
    assert result.balance_btc == "0.00500000"


def test_transaction_lookup_succeeds_for_known_txid(tmp_path: Path) -> None:
    plugin, _ = make_plugin(
        tmp_path,
        backend=RichFakeWalletBackend(
            FakeWalletBackendState(balance_sats=500_000),
            transaction_payload={"confirmations": 2, "amount_sats": 10_000, "fee_sats": 250},
        ),
    )

    result = plugin.observe_transaction(
        WalletTransactionObservationRequest(
            txid="tx_001",
            expected_amount_sats=10_000,
            expected_fee_sats=250,
        )
    )

    assert result.found is True
    assert result.confirmation_status == "confirmed"
    assert result.mismatch_fields == []


def test_missing_txid_returns_safe_structured_result(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    result = plugin.observe_transaction(
        WalletTransactionObservationRequest(wallet_transaction_id="missing")
    )

    assert result.found is False
    assert result.reason == "txid_missing"


def test_mismatched_amount_fee_is_surfaced_deterministically(tmp_path: Path) -> None:
    plugin, _ = make_plugin(
        tmp_path,
        backend=RichFakeWalletBackend(
            FakeWalletBackendState(balance_sats=500_000),
            transaction_payload={"confirmations": 0, "amount_sats": 9_000, "fee_sats": 400},
        ),
    )

    result = plugin.observe_transaction(
        WalletTransactionObservationRequest(
            txid="tx_001",
            expected_amount_sats=10_000,
            expected_fee_sats=250,
        )
    )

    assert sorted(result.mismatch_fields) == ["amount_sats", "fee_sats"]


def test_observation_failures_generate_audit_records(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(
        tmp_path,
        backend=RichFakeWalletBackend(
            FakeWalletBackendState(balance_sats=500_000),
            fail_lookup=True,
        ),
    )

    result = plugin.observe_transaction(WalletTransactionObservationRequest(txid="tx_001"))

    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)
    assert result.found is False
    assert any(
        cast(dict[str, object], event.payload.get("payload")).get("event_name")
        == "wallet_transaction_observation_failed"
        for event in audit_events
        if isinstance(event.payload.get("payload"), dict)
    )


def test_no_spend_capable_path_exists_through_plugin_api(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="read_only"):
        make_plugin(tmp_path, read_only=False)
