"""Models for read-only wallet observations."""

from __future__ import annotations

from pydantic import Field, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class WalletBalanceObservationRequest(MoneyBotModel):
    """Balance observation request."""

    asset: str = "BTC"
    related_record_id: str = "wallet_observer"


class WalletBalanceObservationResult(MoneyBotModel):
    """Read-only balance observation result."""

    observation_id: str
    asset: str
    balance_sats: int = Field(ge=0)
    balance_btc: str
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord


class WalletTransactionObservationRequest(MoneyBotModel):
    """Observation request for one wallet transaction."""

    txid: str | None = None
    wallet_transaction_id: str | None = None
    related_record_id: str = "wallet_observer"
    expected_amount_sats: int | None = Field(default=None, ge=0)
    expected_fee_sats: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_reference(self) -> WalletTransactionObservationRequest:
        if self.txid is None and self.wallet_transaction_id is None:
            msg = "Either txid or wallet_transaction_id is required."
            raise ValueError(msg)
        return self


class WalletTransactionObservationResult(MoneyBotModel):
    """Read-only transaction observation output."""

    observation_id: str
    found: bool
    txid: str | None = None
    confirmation_status: str
    confirmations: int | None = Field(default=None, ge=0)
    observed_amount_sats: int | None = Field(default=None, ge=0)
    observed_fee_sats: int | None = Field(default=None, ge=0)
    mismatch_fields: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
    reason: str | None = None
