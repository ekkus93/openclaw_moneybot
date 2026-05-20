"""Contracts for the wallet governor client skill."""

from __future__ import annotations

from pydantic import Field, HttpUrl, JsonValue, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel


class WalletBalanceRequest(MoneyBotModel):
    """Request the wallet balance for one asset."""

    asset: str = "BTC"
    btc_usd_rate: float | None = Field(default=None, gt=0)


class WalletBalanceResult(MoneyBotModel):
    """Normalized wallet balance result."""

    asset: str
    confirmed_balance: str
    unconfirmed_balance: str = "0"
    usd_estimate: float = Field(ge=0)
    daily_spend_remaining_usd: float = Field(ge=0)
    service_limits: dict[str, JsonValue]


class WalletLimitCheck(MoneyBotModel):
    """Limit checks returned alongside quote/spend responses."""

    single_spend_ok: bool
    daily_spend_ok: bool
    weekly_spend_ok: bool
    wallet_balance_ok: bool


class WalletQuoteSkillRequest(MoneyBotModel):
    """Quote request for a potential governed payment."""

    asset: str = "BTC"
    amount_usd: float = Field(gt=0)
    destination: str
    btc_usd_rate: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_destination(self) -> WalletQuoteSkillRequest:
        if not self.destination.strip():
            msg = "destination is required."
            raise ValueError(msg)
        return self


class WalletQuoteSkillResult(MoneyBotModel):
    """Normalized quote result."""

    operation: str = "quote-spend"
    status: str
    asset: str
    reason: str | None = None
    amount_usd_estimate: float
    amount_asset_estimate: str | None = None
    estimated_fee_asset: str | None = None
    estimated_fee_usd: float = Field(ge=0)
    total_usd_estimate: float | None = Field(default=None, ge=0)
    limit_check: WalletLimitCheck
    rejection_reasons: list[str] = Field(default_factory=list)
    raw_response: dict[str, JsonValue] = Field(default_factory=dict)


class WalletSpendRequest(MoneyBotModel):
    """Client-side spend request."""

    spend_request_id: str | None = None
    opportunity_id: str | None = None
    policy_decision_id: str
    budget_plan_id: str
    tos_legal_check_id: str | None = None
    ledger_event_id: str
    amount_usd: float = Field(gt=0)
    asset: str
    destination: str
    counterparty: str
    purpose: str
    category: str
    source_url: HttpUrl | None = None
    evidence_archive_ids: list[str] = Field(default_factory=list)
    receipt_expected: bool = True
    send_all: bool = False
    btc_usd_rate: float = Field(gt=0)
    idempotency_key: str

    @model_validator(mode="after")
    def validate_required_fields(self) -> WalletSpendRequest:
        if self.send_all:
            msg = "send_all is prohibited."
            raise ValueError(msg)
        required_text_fields = {
            "ledger_event_id": self.ledger_event_id,
            "destination": self.destination,
            "counterparty": self.counterparty,
            "purpose": self.purpose,
            "category": self.category,
            "idempotency_key": self.idempotency_key,
        }
        for field_name, value in required_text_fields.items():
            if not value.strip():
                msg = f"{field_name} is required."
                raise ValueError(msg)
        return self


class WalletSpendResult(MoneyBotModel):
    """Normalized spend result."""

    operation: str = "send-small-payment"
    status: str
    spend_request_id: str | None = None
    wallet_transaction_id: str | None = None
    chain: str = "bitcoin"
    asset: str
    amount_asset: str | None = None
    amount_usd_estimate: float
    fee_asset: str | None = None
    fee_usd_estimate: float = Field(ge=0)
    destination: str
    txid_or_signature: str | None = None
    rejection_reasons: list[str] = Field(default_factory=list)
    receipt_required: bool = True
    ledger_recorded: bool = False
    wallet_governor_decision_id: str | None = None
    raw_response_evidence_id: str | None = None
