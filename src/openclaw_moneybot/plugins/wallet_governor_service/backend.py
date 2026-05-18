"""Wallet backend abstractions, fake backend, and Bitcoin Core skeleton."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

import httpx

from openclaw_moneybot.utils.ids import make_id

SATOSHIS_PER_BTC = Decimal("100000000")
ESTIMATED_TX_VBYTES = Decimal("250")


class WalletBackendError(RuntimeError):
    """Raised when the wallet backend cannot complete a safe operation."""


@dataclass(frozen=True)
class WalletQuoteDetails:
    """Backend-level quote details for a send."""

    amount_sats: int
    fee_sats: int


@dataclass(frozen=True)
class BitcoinCoreRpcConfig:
    """Service-only Bitcoin Core RPC configuration."""

    rpc_url: str
    rpc_user: str
    rpc_password: str
    wallet_name: str
    network: str = "regtest"
    timeout_seconds: float = 5.0
    enabled: bool = False
    passphrase_env_var: str | None = None

    @classmethod
    def from_env(cls, prefix: str = "MONEYBOT_BITCOIN_CORE_") -> BitcoinCoreRpcConfig:
        """Load a disabled-by-default RPC config from environment variables."""
        return cls(
            rpc_url=os.environ.get(f"{prefix}URL", "http://127.0.0.1:18443"),
            rpc_user=os.environ.get(f"{prefix}USER", ""),
            rpc_password=os.environ.get(f"{prefix}PASSWORD", ""),
            wallet_name=os.environ.get(f"{prefix}WALLET", "moneybot"),
            network=os.environ.get(f"{prefix}NETWORK", "regtest"),
            timeout_seconds=float(os.environ.get(f"{prefix}TIMEOUT", "5.0")),
            enabled=os.environ.get(f"{prefix}ENABLED", "false").lower() == "true",
            passphrase_env_var=os.environ.get(f"{prefix}PASSPHRASE_ENV_VAR"),
        )


class WalletBackend(Protocol):
    """Minimal backend contract for wallet operations."""

    backend_name: str

    def health_check(self) -> dict[str, Any]: ...

    def get_balance_sats(self) -> int: ...

    def estimate_fee_sats(self, amount_sats: int) -> int: ...

    def quote_send(self, destination: str, amount_sats: int) -> WalletQuoteDetails: ...

    def unlock(self, seconds: int) -> None: ...

    def lock(self) -> None: ...

    def send_to_address(self, destination: str, amount_sats: int) -> str: ...

    def get_transaction(self, txid: str) -> dict[str, Any]: ...


@dataclass
class FakeWalletBackendState:
    """Observable fake backend state for tests."""

    balance_sats: int
    last_unlock_seconds: int = 0
    lock_count: int = 0
    send_count: int = 0


class FakeWalletBackend:
    """Deterministic in-memory BTC backend."""

    backend_name = "fake"

    def __init__(self, state: FakeWalletBackendState, *, fee_bps: int = 100) -> None:
        self.state = state
        self.fee_bps = fee_bps

    def health_check(self) -> dict[str, Any]:
        return {"backend": self.backend_name, "ok": True}

    def get_balance_sats(self) -> int:
        return self.state.balance_sats

    def estimate_fee_sats(self, amount_sats: int) -> int:
        return max(250, (amount_sats * self.fee_bps) // 10_000)

    def quote_send(self, destination: str, amount_sats: int) -> WalletQuoteDetails:
        del destination
        return WalletQuoteDetails(
            amount_sats=amount_sats,
            fee_sats=self.estimate_fee_sats(amount_sats),
        )

    def unlock(self, seconds: int) -> None:
        self.state.last_unlock_seconds = seconds

    def lock(self) -> None:
        self.state.lock_count += 1

    def send_to_address(self, destination: str, amount_sats: int) -> str:
        del destination
        fee_sats = self.estimate_fee_sats(amount_sats)
        total_sats = amount_sats + fee_sats
        if total_sats > self.state.balance_sats:
            msg = "Insufficient balance."
            raise WalletBackendError(msg)
        self.state.balance_sats -= total_sats
        self.state.send_count += 1
        return make_id("tx")

    def get_transaction(self, txid: str) -> dict[str, Any]:
        return {"txid": txid, "backend": self.backend_name}


class BitcoinCoreWalletBackend:
    """Disabled-by-default Bitcoin Core RPC backend skeleton."""

    backend_name = "bitcoin_core"

    def __init__(
        self,
        config: BitcoinCoreRpcConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self._client = httpx.Client(
            base_url=f"{config.rpc_url.rstrip('/')}/wallet/{config.wallet_name}",
            timeout=config.timeout_seconds,
            auth=(config.rpc_user, config.rpc_password),
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def health_check(self) -> dict[str, Any]:
        result = self._rpc("getblockchaininfo")
        return {
            "backend": self.backend_name,
            "chain": result.get("chain", self.config.network),
            "initialblockdownload": result.get("initialblockdownload", False),
        }

    def get_balance_sats(self) -> int:
        balance_btc = self._rpc("getbalance")
        if not isinstance(balance_btc, int | float | str):
            msg = "Bitcoin Core returned a non-numeric balance."
            raise WalletBackendError(msg)
        return self._btc_to_sats(Decimal(str(balance_btc)))

    def estimate_fee_sats(self, amount_sats: int) -> int:
        del amount_sats
        result = self._rpc("estimatesmartfee", [1])
        if not isinstance(result, dict):
            msg = "Bitcoin Core fee estimate payload was malformed."
            raise WalletBackendError(msg)
        fee_rate = result.get("feerate")
        if not isinstance(fee_rate, int | float | str):
            msg = "Bitcoin Core fee estimate did not include feerate."
            raise WalletBackendError(msg)
        sats_per_kvb = Decimal(str(fee_rate)) * SATOSHIS_PER_BTC
        fee_sats = (sats_per_kvb * ESTIMATED_TX_VBYTES) / Decimal("1000")
        return max(int(fee_sats.quantize(Decimal("1"), rounding=ROUND_HALF_UP)), 250)

    def quote_send(self, destination: str, amount_sats: int) -> WalletQuoteDetails:
        del destination
        return WalletQuoteDetails(
            amount_sats=amount_sats,
            fee_sats=self.estimate_fee_sats(amount_sats),
        )

    def unlock(self, seconds: int) -> None:
        passphrase_env_var = self.config.passphrase_env_var
        if passphrase_env_var is None:
            return
        passphrase = os.environ.get(passphrase_env_var)
        if not passphrase:
            msg = "Configured wallet passphrase environment variable is missing."
            raise WalletBackendError(msg)
        self._rpc("walletpassphrase", [passphrase, seconds])

    def lock(self) -> None:
        if self.config.passphrase_env_var is None:
            return
        self._rpc("walletlock")

    def send_to_address(self, destination: str, amount_sats: int) -> str:
        txid = self._rpc("sendtoaddress", [destination, self._sats_to_btc(amount_sats)])
        if not isinstance(txid, str) or not txid:
            msg = "Bitcoin Core send did not return a transaction id."
            raise WalletBackendError(msg)
        return txid

    def get_transaction(self, txid: str) -> dict[str, Any]:
        result = self._rpc("gettransaction", [txid])
        if not isinstance(result, dict):
            msg = "Bitcoin Core transaction payload was malformed."
            raise WalletBackendError(msg)
        return result

    def _rpc(self, method: str, params: list[Any] | None = None) -> Any:
        if not self.config.enabled:
            msg = "Bitcoin Core backend is disabled."
            raise WalletBackendError(msg)
        try:
            response = self._client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": make_id("rpc"),
                    "method": method,
                    "params": params or [],
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            msg = f"Bitcoin Core RPC request failed for {method}."
            raise WalletBackendError(msg) from error
        payload = response.json()
        if not isinstance(payload, dict):
            msg = "Bitcoin Core RPC response was not a JSON object."
            raise WalletBackendError(msg)
        error_payload = payload.get("error")
        if error_payload is not None:
            msg = f"Bitcoin Core RPC returned an error for {method}."
            raise WalletBackendError(msg)
        return payload.get("result")

    @staticmethod
    def _btc_to_sats(amount_btc: Decimal) -> int:
        sats = amount_btc * SATOSHIS_PER_BTC
        return int(sats.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def _sats_to_btc(amount_sats: int) -> str:
        btc_amount = Decimal(amount_sats) / SATOSHIS_PER_BTC
        return str(btc_amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))
