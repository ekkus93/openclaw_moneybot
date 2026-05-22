"""Models for bounded crypto market data lookups."""

from __future__ import annotations

from pydantic import Field, JsonValue, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class CryptoSpotPriceRequest(MoneyBotModel):
    """One bounded crypto spot-price lookup."""

    asset_id: str = Field(min_length=1, max_length=64)
    vs_currency: str = Field(default="usd", min_length=1, max_length=16)

    @field_validator("asset_id", "vs_currency")
    @classmethod
    def normalize_identifiers(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            msg = "Identifier fields must not be empty."
            raise ValueError(msg)
        return normalized


class CryptoSpotPriceResult(MoneyBotModel):
    """Normalized crypto spot-price response."""

    lookup_id: str
    asset_id: str
    vs_currency: str
    price: float
    market_cap: float | None = None
    total_volume_24h: float | None = None
    change_24h_percent: float | None = None
    last_updated_at_unix: int | None = None
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord


class CryptoMarketChartRequest(MoneyBotModel):
    """One bounded recent market-chart request."""

    asset_id: str = Field(min_length=1, max_length=64)
    vs_currency: str = Field(default="usd", min_length=1, max_length=16)
    days: int = Field(default=7, gt=0, le=365)
    count: int = Field(default=10, gt=0, le=100)

    @field_validator("asset_id", "vs_currency")
    @classmethod
    def normalize_identifiers(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            msg = "Identifier fields must not be empty."
            raise ValueError(msg)
        return normalized


class CryptoMarketChartPoint(MoneyBotModel):
    """One normalized market-chart point."""

    timestamp_ms: int = Field(ge=0)
    price: float
    market_cap: float | None = None
    total_volume: float | None = None


class CryptoMarketChartResult(MoneyBotModel):
    """Normalized recent market-chart response."""

    lookup_id: str
    asset_id: str
    vs_currency: str
    days: int = Field(gt=0)
    result_count: int = Field(ge=0)
    points: list[CryptoMarketChartPoint] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
