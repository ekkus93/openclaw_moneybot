"""Read-only wallet observation plugin."""

from openclaw_moneybot.plugins.wallet_observer_plugin.models import (
    WalletBalanceObservationRequest,
    WalletBalanceObservationResult,
    WalletTransactionObservationRequest,
    WalletTransactionObservationResult,
)
from openclaw_moneybot.plugins.wallet_observer_plugin.service import WalletObserverPlugin

__all__ = [
    "WalletBalanceObservationRequest",
    "WalletBalanceObservationResult",
    "WalletObserverPlugin",
    "WalletTransactionObservationRequest",
    "WalletTransactionObservationResult",
]
