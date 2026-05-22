"""Unit tests for the stock market data plugin."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from openclaw_moneybot.plugins.stock_market_data_plugin import (
    StockDailyBarsRequest,
    StockMarketDataPlugin,
    StockMarketDataPluginError,
    StockQuoteRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, StockMarketDataConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(
    tmp_path: Path,
    *,
    enabled: bool = True,
    handler: httpx.BaseTransport | None = None,
) -> tuple[StockMarketDataPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = StockMarketDataPlugin(
        StockMarketDataConfig(
            enabled=enabled,
            max_daily_bars=10,
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def test_get_quote_returns_normalized_quote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.alphavantage.co"
        assert request.url.path == "/query"
        assert request.url.params["function"] == "GLOBAL_QUOTE"
        assert request.url.params["symbol"] == "IBM"
        assert request.url.params["apikey"] == "demo-key"
        return httpx.Response(
            200,
            json={
                "Global Quote": {
                    "01. symbol": "IBM",
                    "02. open": "100.00",
                    "03. high": "105.00",
                    "04. low": "99.50",
                    "05. price": "103.25",
                    "06. volume": "123456",
                    "07. latest trading day": "2026-05-21",
                    "08. previous close": "101.00",
                    "09. change": "2.25",
                    "10. change percent": "2.2277%",
                }
            },
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.get_quote(StockQuoteRequest(symbol="ibm"))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.STOCK_MARKET_DATA,
        related_id=result.lookup_id,
    )

    assert result.symbol == "IBM"
    assert result.price == 103.25
    assert result.change_percent == 2.2277
    assert result.volume == 123456
    assert evidence[0].evidence_type == "alpha_vantage_global_quote_response"


def test_get_daily_bars_returns_bounded_recent_series(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["function"] == "TIME_SERIES_DAILY"
        assert request.url.params["outputsize"] == "compact"
        return httpx.Response(
            200,
            json={
                "Meta Data": {
                    "2. Symbol": "IBM",
                    "3. Last Refreshed": "2026-05-21",
                },
                "Time Series (Daily)": {
                    "2026-05-21": {
                        "1. open": "100.00",
                        "2. high": "101.00",
                        "3. low": "99.50",
                        "4. close": "100.50",
                        "5. volume": "1000",
                    },
                    "2026-05-20": {
                        "1. open": "98.00",
                        "2. high": "100.00",
                        "3. low": "97.50",
                        "4. close": "99.25",
                        "5. volume": "2000",
                    },
                    "2026-05-19": {
                        "1. open": "97.00",
                        "2. high": "98.50",
                        "3. low": "96.50",
                        "4. close": "98.00",
                        "5. volume": "3000",
                    },
                },
            },
        )

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.get_daily_bars(StockDailyBarsRequest(symbol="IBM", count=2))

    assert result.symbol == "IBM"
    assert result.last_refreshed == "2026-05-21"
    assert result.result_count == 2
    assert result.bars[0].trading_day == "2026-05-21"
    assert result.bars[1].close_price == 99.25


def test_get_quote_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.get_quote(StockQuoteRequest(symbol="IBM"))


def test_get_quote_rejects_without_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(StockMarketDataPluginError, match="ALPHA_VANTAGE_API_KEY"):
        plugin.get_quote(StockQuoteRequest(symbol="IBM"))


def test_get_quote_rejects_provider_error_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"Note": "Thank you for using Alpha Vantage! Please visit premium."},
        )

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(StockMarketDataPluginError, match="Thank you for using Alpha Vantage"):
        plugin.get_quote(StockQuoteRequest(symbol="IBM"))


def test_get_daily_bars_surfaces_transport_failures_as_plugin_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo-key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(StockMarketDataPluginError, match="unavailable"):
        plugin.get_daily_bars(StockDailyBarsRequest(symbol="IBM", count=2))
