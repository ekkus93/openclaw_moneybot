"""Tests for the Bitcoin Core wallet backend skeleton."""

from __future__ import annotations

import json

import httpx

from openclaw_moneybot.plugins.wallet_governor_service import (
    BitcoinCoreRpcConfig,
    BitcoinCoreWalletBackend,
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

    txid = backend.send_to_address("bcrt1qmoneybotdest123", 10_000)

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
