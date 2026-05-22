"""Models for bounded stock market data lookups."""

from __future__ import annotations

from pydantic import Field, JsonValue, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class StockQuoteRequest(MoneyBotModel):
    """One bounded stock quote lookup."""

    symbol: str = Field(min_length=1, max_length=32)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            msg = "symbol must not be empty"
            raise ValueError(msg)
        return normalized


class StockQuoteResult(MoneyBotModel):
    """Normalized stock quote response."""

    lookup_id: str
    symbol: str
    price: float
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    previous_close: float | None = None
    change_amount: float | None = None
    change_percent: float | None = None
    latest_trading_day: str | None = None
    volume: int | None = Field(default=None, ge=0)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord


class StockDailyBarsRequest(MoneyBotModel):
    """One bounded daily-bars request."""

    symbol: str = Field(min_length=1, max_length=32)
    count: int = Field(default=5, gt=0, le=100)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            msg = "symbol must not be empty"
            raise ValueError(msg)
        return normalized


class StockDailyBar(MoneyBotModel):
    """One normalized daily OHLCV bar."""

    trading_day: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int = Field(ge=0)


class StockDailyBarsResult(MoneyBotModel):
    """Normalized daily-bars response."""

    lookup_id: str
    symbol: str
    last_refreshed: str | None = None
    result_count: int = Field(ge=0)
    bars: list[StockDailyBar] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
