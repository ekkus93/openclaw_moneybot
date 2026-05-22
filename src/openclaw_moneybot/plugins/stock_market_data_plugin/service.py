"""Read-only Alpha Vantage stock market data integration."""

from __future__ import annotations

import os
from typing import TypedDict

import httpx

from openclaw_moneybot.plugins.stock_market_data_plugin.models import (
    StockDailyBar,
    StockDailyBarsRequest,
    StockDailyBarsResult,
    StockQuoteRequest,
    StockQuoteResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, StockMarketDataConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class _NormalizedQuote(TypedDict):
    symbol: str
    price: float
    open_price: float | None
    high_price: float | None
    low_price: float | None
    previous_close: float | None
    change_amount: float | None
    change_percent: float | None
    latest_trading_day: str | None
    volume: int | None


QueryValue = str | int | float | bool | None


class StockMarketDataPluginError(RuntimeError):
    """Raised when stock market data cannot be retrieved safely."""


class StockMarketDataPlugin:
    """Fetch bounded stock quotes and daily bars through Alpha Vantage."""

    def __init__(
        self,
        config: StockMarketDataConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
        self.ledger_service = ledger_service
        self._client = httpx.Client(timeout=config.timeout_seconds, transport=transport)

    def close(self) -> None:
        self._client.close()

    def health(self) -> PluginHealthResult:
        """Return plugin status, including missing credential state."""

        return PluginHealthResult(
            plugin_name="stock_market_data_plugin",
            enabled=self.config.enabled,
            read_only=True,
            status="ok" if self._api_key() is not None else "missing_api_key",
        )

    def get_quote(self, request: StockQuoteRequest) -> StockQuoteResult:
        """Fetch one bounded stock quote."""

        self._ensure_enabled()
        api_key = self._required_api_key()
        lookup_id = make_id("stock")
        payload = self._query(
            lookup_id=lookup_id,
            event_name="stock_quote_failed",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": request.symbol,
                "apikey": api_key,
            },
        )
        raw_quote = payload.get("Global Quote")
        if not isinstance(raw_quote, dict):
            msg = "Alpha Vantage quote response is missing Global Quote."
            raise StockMarketDataPluginError(msg)
        quote = self._normalize_quote(raw_quote)
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.STOCK_MARKET_DATA,
            related_id=lookup_id,
            evidence_type="alpha_vantage_global_quote_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded Alpha Vantage stock quote response snapshot",
        )
        summary = {
            "provider": "alpha_vantage",
            "symbol": quote["symbol"],
            "latest_trading_day": quote["latest_trading_day"],
            "price": quote["price"],
            "change_percent": quote["change_percent"],
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.STOCK_MARKET_DATA,
            related_record_id=lookup_id,
            payload={
                "provider": "alpha_vantage",
                "mode": "quote",
                "symbol": quote["symbol"],
                "price": quote["price"],
                "latest_trading_day": quote["latest_trading_day"],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return StockQuoteResult(
            lookup_id=lookup_id,
            symbol=quote["symbol"],
            price=quote["price"],
            open_price=quote["open_price"],
            high_price=quote["high_price"],
            low_price=quote["low_price"],
            previous_close=quote["previous_close"],
            change_amount=quote["change_amount"],
            change_percent=quote["change_percent"],
            latest_trading_day=quote["latest_trading_day"],
            volume=quote["volume"],
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def get_daily_bars(self, request: StockDailyBarsRequest) -> StockDailyBarsResult:
        """Fetch one bounded recent daily-bars series."""

        self._ensure_enabled()
        if request.count > self.config.max_daily_bars:
            msg = "Requested bar count exceeds the configured maximum."
            raise ValueError(msg)
        api_key = self._required_api_key()
        lookup_id = make_id("stock")
        payload = self._query(
            lookup_id=lookup_id,
            event_name="stock_daily_bars_failed",
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": request.symbol,
                "outputsize": "compact",
                "apikey": api_key,
            },
        )
        symbol, bars, last_refreshed = self._normalize_daily_bars(
            payload,
            symbol=request.symbol,
            count=request.count,
        )
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.STOCK_MARKET_DATA,
            related_id=lookup_id,
            evidence_type="alpha_vantage_daily_bars_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded Alpha Vantage daily-bars response snapshot",
        )
        summary = {
            "provider": "alpha_vantage",
            "symbol": symbol,
            "last_refreshed": last_refreshed,
            "trading_days": [item.trading_day for item in bars],
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.STOCK_MARKET_DATA,
            related_record_id=lookup_id,
            payload={
                "provider": "alpha_vantage",
                "mode": "daily_bars",
                "symbol": symbol,
                "result_count": len(bars),
                "last_refreshed": last_refreshed,
                "trading_days": [item.trading_day for item in bars],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return StockDailyBarsResult(
            lookup_id=lookup_id,
            symbol=symbol,
            last_refreshed=last_refreshed,
            result_count=len(bars),
            bars=bars,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def _api_key(self) -> str | None:
        token = os.environ.get(self.config.api_key_env_var)
        if token is None:
            return None
        normalized = token.strip()
        return None if normalized == "" else normalized

    def _ensure_enabled(self) -> None:
        if not self.config.enabled:
            msg = "stock_market_data_plugin is disabled."
            raise ValueError(msg)

    def _required_api_key(self) -> str:
        api_key = self._api_key()
        if api_key is None:
            msg = f"Missing Alpha Vantage API key in {self.config.api_key_env_var}."
            raise StockMarketDataPluginError(msg)
        return api_key

    def _query(
        self,
        *,
        lookup_id: str,
        event_name: str,
        params: dict[str, QueryValue],
    ) -> dict[str, object]:
        try:
            response = self._client.get(
                self.config.api_base_url,
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(lookup_id, event_name, reason="transport_error")
            msg = "Alpha Vantage market data is unavailable."
            raise StockMarketDataPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            self._record_failure(lookup_id, event_name, reason="invalid_response")
            msg = f"Alpha Vantage request failed: {error}"
            raise StockMarketDataPluginError(msg) from error
        if not isinstance(payload, dict):
            msg = "Alpha Vantage response must be a JSON object."
            raise StockMarketDataPluginError(msg)
        provider_error = self._provider_error_message(payload)
        if provider_error is not None:
            self._record_failure(
                lookup_id,
                event_name,
                reason="provider_error",
                provider_error=provider_error,
            )
            msg = f"Alpha Vantage request failed: {provider_error}"
            raise StockMarketDataPluginError(msg)
        return payload

    def _record_failure(self, lookup_id: str, event_name: str, **payload: object) -> None:
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=lookup_id,
            event_name=event_name,
            payload=payload,
        )

    @staticmethod
    def _provider_error_message(payload: dict[str, object]) -> str | None:
        for key in ("Error Message", "Note", "Information"):
            value = payload.get(key)
            if isinstance(value, str):
                normalized = value.strip()
                if normalized:
                    return normalized
        return None

    def _normalize_quote(self, payload: dict[str, object]) -> _NormalizedQuote:
        symbol = self._required_string(payload.get("01. symbol"), "symbol")
        return {
            "symbol": symbol,
            "price": self._required_float(payload.get("05. price"), "price"),
            "open_price": self._optional_float(payload.get("02. open")),
            "high_price": self._optional_float(payload.get("03. high")),
            "low_price": self._optional_float(payload.get("04. low")),
            "previous_close": self._optional_float(payload.get("08. previous close")),
            "change_amount": self._optional_float(payload.get("09. change")),
            "change_percent": self._optional_percentage(payload.get("10. change percent")),
            "latest_trading_day": self._optional_string(payload.get("07. latest trading day")),
            "volume": self._optional_int(payload.get("06. volume")),
        }

    def _normalize_daily_bars(
        self,
        payload: dict[str, object],
        *,
        symbol: str,
        count: int,
    ) -> tuple[str, list[StockDailyBar], str | None]:
        raw_series = payload.get("Time Series (Daily)")
        if not isinstance(raw_series, dict):
            msg = "Alpha Vantage daily-bars response is missing Time Series (Daily)."
            raise StockMarketDataPluginError(msg)
        meta_data = payload.get("Meta Data")
        last_refreshed: str | None = None
        if isinstance(meta_data, dict):
            last_refreshed = self._optional_string(meta_data.get("3. Last Refreshed"))
            provider_symbol = self._optional_string(meta_data.get("2. Symbol"))
            if provider_symbol is not None and provider_symbol != symbol:
                symbol = provider_symbol
        bars: list[StockDailyBar] = []
        for trading_day in sorted(raw_series.keys(), reverse=True):
            if len(bars) >= count:
                break
            bar_payload = raw_series.get(trading_day)
            if not isinstance(bar_payload, dict):
                continue
            bars.append(
                StockDailyBar(
                    trading_day=trading_day,
                    open_price=self._required_float(bar_payload.get("1. open"), "open"),
                    high_price=self._required_float(bar_payload.get("2. high"), "high"),
                    low_price=self._required_float(bar_payload.get("3. low"), "low"),
                    close_price=self._required_float(bar_payload.get("4. close"), "close"),
                    volume=self._required_int(bar_payload.get("5. volume"), "volume"),
                )
            )
        if not bars:
            msg = "Alpha Vantage daily-bars response did not contain any bars."
            raise StockMarketDataPluginError(msg)
        return symbol, bars, last_refreshed

    @staticmethod
    def _required_string(value: object, field_name: str) -> str:
        if not isinstance(value, str):
            msg = f"Alpha Vantage response is missing {field_name}."
            raise StockMarketDataPluginError(msg)
        normalized = value.strip()
        if not normalized:
            msg = f"Alpha Vantage response is missing {field_name}."
            raise StockMarketDataPluginError(msg)
        return normalized

    @staticmethod
    def _required_float(value: object, field_name: str) -> float:
        if not isinstance(value, str):
            msg = f"Alpha Vantage response is missing {field_name}."
            raise StockMarketDataPluginError(msg)
        try:
            return float(value)
        except ValueError as error:
            msg = f"Alpha Vantage response has invalid {field_name}."
            raise StockMarketDataPluginError(msg) from error

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if normalized == "":
            return None
        try:
            return float(normalized)
        except ValueError as error:
            msg = "Alpha Vantage response has invalid numeric data."
            raise StockMarketDataPluginError(msg) from error

    @staticmethod
    def _required_int(value: object, field_name: str) -> int:
        if not isinstance(value, str):
            msg = f"Alpha Vantage response is missing {field_name}."
            raise StockMarketDataPluginError(msg)
        try:
            return int(value)
        except ValueError as error:
            msg = f"Alpha Vantage response has invalid {field_name}."
            raise StockMarketDataPluginError(msg) from error

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if normalized == "":
            return None
        try:
            return int(normalized)
        except ValueError as error:
            msg = "Alpha Vantage response has invalid integer data."
            raise StockMarketDataPluginError(msg) from error

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return None if normalized == "" else normalized

    @staticmethod
    def _optional_percentage(value: object) -> float | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().removesuffix("%")
        if normalized == "":
            return None
        try:
            return float(normalized)
        except ValueError as error:
            msg = "Alpha Vantage response has invalid percentage data."
            raise StockMarketDataPluginError(msg) from error
