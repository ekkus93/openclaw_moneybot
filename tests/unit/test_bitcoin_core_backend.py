"""Tests for the Bitcoin Core wallet backend skeleton."""

from __future__ import annotations

import json

import httpx
import pytest

from openclaw_moneybot.plugins.wallet_governor_service import (
    BitcoinCoreRpcConfig,
    BitcoinCoreWalletBackend,
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletBackendError,
)


def make_backend(handler: httpx.MockTransport) -> BitcoinCoreWalletBackend:
    config = BitcoinCoreRpcConfig(
        rpc_url="http://127.0.0.1:18443",
        rpc_user="user",
        rpc_password="pass",
        wallet_name="moneybot",
        enabled=True,
    )
    return BitcoinCoreWalletBackend(config, transport=handler)


def test_balance_parsing_uses_fake_rpc() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["method"] == "getbalance"
        return httpx.Response(200, json={"result": "0.01000000", "error": None})

    backend = make_backend(httpx.MockTransport(handler))

    assert backend.get_balance_sats() == 1_000_000


def test_fee_estimate_parsing_uses_fake_rpc() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["method"] == "estimatesmartfee"
        return httpx.Response(200, json={"result": {"feerate": "0.00001000"}, "error": None})

    backend = make_backend(httpx.MockTransport(handler))

    assert backend.estimate_fee_sats(10_000) >= 250


def test_successful_send_uses_expected_rpc_call() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        methods.append(str(payload["method"]))
        if payload["method"] == "sendtoaddress":
            return httpx.Response(200, json={"result": "txid_001", "error": None})
        raise AssertionError(f"Unexpected method: {payload['method']}")

    backend = make_backend(httpx.MockTransport(handler))

    txid = backend.send_to_address("bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2", 10_000)

    assert txid == "txid_001"
    assert methods == ["sendtoaddress"]


def test_rpc_errors_become_typed_backend_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"result": None, "error": {"code": -1}})

    backend = make_backend(httpx.MockTransport(handler))

    try:
        backend.get_transaction("txid_001")
    except WalletBackendError as error:
        assert "gettransaction" in str(error)
    else:
        raise AssertionError("Expected RPC errors to become WalletBackendError")


def test_disabled_backend_refuses_rpc_calls() -> None:
    config = BitcoinCoreRpcConfig(
        rpc_url="http://127.0.0.1:18443",
        rpc_user="user",
        rpc_password="pass",
        wallet_name="moneybot",
        enabled=False,
    )
    backend = BitcoinCoreWalletBackend(config)

    try:
        backend.get_balance_sats()
    except WalletBackendError as error:
        assert "disabled" in str(error)
    else:
        raise AssertionError("Expected disabled backend to fail closed")


def test_from_env_loads_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MONEYBOT_BITCOIN_CORE_ENABLED", raising=False)

    config = BitcoinCoreRpcConfig.from_env()

    assert config.rpc_url == "http://127.0.0.1:18443"
    assert config.wallet_name == "moneybot"
    assert config.enabled is False


def test_from_env_parses_enabled_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONEYBOT_BITCOIN_CORE_ENABLED", "true")

    config = BitcoinCoreRpcConfig.from_env()

    assert config.enabled is True


def test_balance_rejects_non_numeric_payload() -> None:
    backend = make_backend(
        httpx.MockTransport(lambda request: httpx.Response(200, json={"result": [], "error": None}))
    )

    with pytest.raises(WalletBackendError):
        backend.get_balance_sats()


def test_fee_estimate_rejects_non_dict_payload() -> None:
    backend = make_backend(
        httpx.MockTransport(lambda request: httpx.Response(200, json={"result": [], "error": None}))
    )

    with pytest.raises(WalletBackendError):
        backend.estimate_fee_sats(10_000)


def test_fee_estimate_rejects_missing_feerate() -> None:
    backend = make_backend(
        httpx.MockTransport(lambda request: httpx.Response(200, json={"result": {}, "error": None}))
    )

    with pytest.raises(WalletBackendError):
        backend.estimate_fee_sats(10_000)


def test_send_rejects_empty_txid() -> None:
    backend = make_backend(
        httpx.MockTransport(lambda request: httpx.Response(200, json={"result": "", "error": None}))
    )

    with pytest.raises(WalletBackendError):
        backend.send_to_address("bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2", 10_000)


def test_get_transaction_rejects_non_dict_result() -> None:
    backend = make_backend(
        httpx.MockTransport(lambda request: httpx.Response(200, json={"result": [], "error": None}))
    )

    with pytest.raises(WalletBackendError):
        backend.get_transaction("txid_001")


def test_unlock_raises_when_passphrase_env_var_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    config = BitcoinCoreRpcConfig(
        rpc_url="http://127.0.0.1:18443",
        rpc_user="user",
        rpc_password="pass",
        wallet_name="moneybot",
        enabled=True,
        passphrase_env_var="MISSING_PASSPHRASE",
    )
    monkeypatch.delenv("MISSING_PASSPHRASE", raising=False)
    backend = BitcoinCoreWalletBackend(config)

    with pytest.raises(WalletBackendError):
        backend.unlock(5)


def test_unlock_uses_passphrase_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        methods.append(str(payload["method"]))
        assert payload["params"] == ["secret", 5]
        return httpx.Response(200, json={"result": None, "error": None})

    monkeypatch.setenv("MONEYBOT_PASS", "secret")
    config = BitcoinCoreRpcConfig(
        rpc_url="http://127.0.0.1:18443",
        rpc_user="user",
        rpc_password="pass",
        wallet_name="moneybot",
        enabled=True,
        passphrase_env_var="MONEYBOT_PASS",
    )
    backend = BitcoinCoreWalletBackend(config, transport=httpx.MockTransport(handler))

    backend.unlock(5)

    assert methods == ["walletpassphrase"]


def test_lock_is_noop_without_passphrase_support() -> None:
    backend = make_backend(httpx.MockTransport(lambda request: httpx.Response(200)))

    backend.lock()


def test_rpc_wraps_http_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    backend = make_backend(httpx.MockTransport(handler))

    with pytest.raises(WalletBackendError):
        backend.get_balance_sats()


def test_rpc_rejects_non_object_json() -> None:
    backend = make_backend(httpx.MockTransport(lambda request: httpx.Response(200, json=[])))

    with pytest.raises(WalletBackendError):
        backend._rpc("getbalance")


def test_fake_backend_fee_floor_and_helpers() -> None:
    backend = FakeWalletBackend(FakeWalletBackendState(balance_sats=1_000))

    assert backend.estimate_fee_sats(1) == 250
    assert backend.health_check() == {"backend": "fake", "ok": True}
    assert backend.get_transaction("tx_123") == {"txid": "tx_123", "backend": "fake"}


def test_send_rejects_invalid_destination_before_rpc() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"result": "txid_001", "error": None})

    backend = make_backend(httpx.MockTransport(handler))

    with pytest.raises(WalletBackendError, match="invalid destination"):
        backend.send_to_address("bc1notvalid!!!!", 10_000)

    assert calls == 0


def test_send_rejects_network_mismatch_before_rpc() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"result": "txid_001", "error": None})

    config = BitcoinCoreRpcConfig(
        rpc_url="http://127.0.0.1:18443",
        rpc_user="user",
        rpc_password="pass",
        wallet_name="moneybot",
        network="mainnet",
        enabled=True,
    )
    backend = BitcoinCoreWalletBackend(config, transport=httpx.MockTransport(handler))

    with pytest.raises(WalletBackendError, match="invalid destination"):
        backend.send_to_address("bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2", 10_000)

    assert calls == 0
