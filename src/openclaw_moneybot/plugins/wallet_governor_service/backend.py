"""Wallet backend abstractions and a deterministic fake backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openclaw_moneybot.utils.ids import make_id


class WalletBackend(Protocol):
    """Minimal backend contract for wallet operations."""

    backend_name: str

    def get_balance_sats(self) -> int: ...

    def estimate_fee_sats(self, amount_sats: int) -> int: ...

    def unlock(self, seconds: int) -> None: ...

    def lock(self) -> None: ...

    def send_to_address(self, destination: str, amount_sats: int) -> str: ...


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

    def get_balance_sats(self) -> int:
        return self.state.balance_sats

    def estimate_fee_sats(self, amount_sats: int) -> int:
        return max(250, (amount_sats * self.fee_bps) // 10_000)

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
            raise ValueError(msg)
        self.state.balance_sats -= total_sats
        self.state.send_count += 1
        return make_id("tx")
