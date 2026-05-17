"""Models for the wallet governor service."""

from __future__ import annotations

from pydantic import Field, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel


class WalletHealthResponse(MoneyBotModel):
    """Health metadata for the local wallet governor."""

    status: str
    spend_enabled: bool
    backend: str
    allowed_assets: list[str]


class WalletBalanceResponse(MoneyBotModel):
    """Wallet balance response."""

    asset: str
    balance_btc: str
    balance_sats: int


class WalletLimitsResponse(MoneyBotModel):
    """Resolved spend limits for the current day/week."""

    asset: str
    spend_enabled: bool
    max_single_usd: float
    max_daily_usd: float
    max_weekly_usd: float
    remaining_daily_usd: float
    remaining_weekly_usd: float


class WalletQuoteRequest(MoneyBotModel):
    """Quote request for a potential send."""

    asset: str
    amount_usd: float = Field(gt=0)
    btc_usd_rate: float = Field(gt=0)
    destination: str


class WalletQuoteResponse(MoneyBotModel):
    """Deterministic quote for a BTC transfer."""

    asset: str
    amount_btc: str
    amount_sats: int
    fee_btc: str
    fee_sats: int
    amount_usd: float
    total_usd: float


class WalletSendRequest(MoneyBotModel):
    """Validated local-only wallet send request."""

    spend_request_id: str | None = None
    opportunity_id: str | None = None
    budget_plan_id: str
    policy_decision_id: str
    ledger_record_id: str
    amount_usd: float = Field(gt=0)
    asset: str
    destination: str
    counterparty: str
    purpose: str
    category: str
    btc_usd_rate: float = Field(gt=0)
    send_all: bool = False
    evidence_archive_ids: list[str] = Field(default_factory=list)
    idempotency_key: str

    @model_validator(mode="after")
    def validate_request(self) -> WalletSendRequest:
        """Reject missing references and send-all behavior."""
        if self.send_all:
            msg = "send_all is prohibited."
            raise ValueError(msg)
        if not self.destination.strip():
            msg = "destination is required."
            raise ValueError(msg)
        if not self.counterparty.strip():
            msg = "counterparty is required."
            raise ValueError(msg)
        if not self.purpose.strip():
            msg = "purpose is required."
            raise ValueError(msg)
        if not self.ledger_record_id.strip():
            msg = "ledger_record_id is required."
            raise ValueError(msg)
        if not self.idempotency_key.strip():
            msg = "idempotency_key is required."
            raise ValueError(msg)
        return self


class WalletSendResponse(MoneyBotModel):
    """Outcome of a wallet-governed send attempt."""

    status: str
    spend_request_id: str | None = None
    wallet_transaction_id: str | None = None
    txid: str | None = None
    amount_btc: str | None = None
    fee_btc: str | None = None
    amount_usd: float | None = None
    reason: str | None = None
