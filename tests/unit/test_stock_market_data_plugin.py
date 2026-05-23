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


def audit_event_payloads(ledger_service: LedgerService) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for event in ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT):
        payload = event.payload.get("payload")
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


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


def test_health_reports_missing_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    plugin, _ = make_plugin(tmp_path)

    assert plugin.health().status == "missing_api_key"


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


def test_get_daily_bars_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.get_daily_bars(StockDailyBarsRequest(symbol="IBM", count=2))


def test_get_daily_bars_rejects_counts_above_max(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="configured maximum"):
        plugin.get_daily_bars(StockDailyBarsRequest(symbol="IBM", count=11))


def test_required_api_key_fails_closed_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(StockMarketDataPluginError, match="ALPHA_VANTAGE_API_KEY"):
        plugin._required_api_key()


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


def test_query_records_transport_error_audit_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo-key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(StockMarketDataPluginError, match="unavailable"):
        plugin.get_quote(StockQuoteRequest(symbol="IBM"))

    assert audit_event_payloads(ledger_service)[-1]["reason"] == "transport_error"


@pytest.mark.parametrize(
    ("response", "match"),
    [
        (httpx.Response(500, text="boom"), "request failed"),
        (httpx.Response(200, text="not-json"), "request failed"),
    ],
)
def test_query_records_invalid_response_audit_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    response: httpx.Response,
    match: str,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return response

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(StockMarketDataPluginError, match=match):
        plugin.get_quote(StockQuoteRequest(symbol="IBM"))

    assert audit_event_payloads(ledger_service)[-1]["reason"] == "invalid_response"


def test_query_rejects_non_object_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["bad"])

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(StockMarketDataPluginError, match="JSON object"):
        plugin._query(lookup_id="stock-test", event_name="failed", params={})


@pytest.mark.parametrize("field", ["Error Message", "Note", "Information"])
def test_query_maps_provider_error_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={field: " provider says no "})

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(StockMarketDataPluginError, match="provider says no"):
        plugin.get_quote(StockQuoteRequest(symbol="IBM"))

    assert audit_event_payloads(ledger_service)[-1]["provider_error"] == "provider says no"


def test_get_quote_rejects_missing_global_quote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(StockMarketDataPluginError, match="missing Global Quote"):
        plugin.get_quote(StockQuoteRequest(symbol="IBM"))


def test_normalize_quote_rejects_missing_required_fields(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(StockMarketDataPluginError, match="missing symbol"):
        plugin._normalize_quote({"05. price": "1.0"})

    with pytest.raises(StockMarketDataPluginError, match="missing price"):
        plugin._normalize_quote({"01. symbol": "IBM"})


def test_normalize_quote_tolerates_missing_optional_numeric_fields(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    quote = plugin._normalize_quote(
        {
            "01. symbol": " IBM ",
            "05. price": "100.0",
            "02. open": " ",
            "03. high": None,
            "04. low": "",
            "06. volume": " ",
            "07. latest trading day": " ",
            "08. previous close": None,
            "09. change": "",
            "10. change percent": None,
        }
    )

    assert quote["symbol"] == "IBM"
    assert quote["open_price"] is None
    assert quote["high_price"] is None
    assert quote["low_price"] is None
    assert quote["volume"] is None
    assert quote["change_amount"] is None
    assert quote["change_percent"] is None


def test_normalize_quote_parses_percentage_strings(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    quote = plugin._normalize_quote(
        {"01. symbol": "IBM", "05. price": "1.0", "10. change percent": " 2.50% "}
    )

    assert quote["change_percent"] == 2.5


def test_normalize_daily_bars_rejects_missing_series(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(StockMarketDataPluginError, match="Time Series"):
        plugin._normalize_daily_bars({}, symbol="IBM", count=1)


def test_normalize_daily_bars_uses_provider_symbol_and_missing_last_refreshed(
    tmp_path: Path,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    symbol, bars, last_refreshed = plugin._normalize_daily_bars(
        {
            "Meta Data": {"2. Symbol": "MSFT", "3. Last Refreshed": "  "},
            "Time Series (Daily)": {
                "2026-05-21": {
                    "1. open": "1",
                    "2. high": "2",
                    "3. low": "0.5",
                    "4. close": "1.5",
                    "5. volume": "10",
                }
            },
        },
        symbol="IBM",
        count=1,
    )

    assert symbol == "MSFT"
    assert last_refreshed is None
    assert bars[0].trading_day == "2026-05-21"


def test_normalize_daily_bars_skips_malformed_rows_and_truncates_count(
    tmp_path: Path,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    symbol, bars, _ = plugin._normalize_daily_bars(
        {
            "Time Series (Daily)": {
                "2026-05-21": {
                    "1. open": "1",
                    "2. high": "2",
                    "3. low": "0.5",
                    "4. close": "1.5",
                    "5. volume": "10",
                },
                "2026-05-20": ["bad"],
                "2026-05-19": {
                    "1. open": "3",
                    "2. high": "4",
                    "3. low": "2.5",
                    "4. close": "3.5",
                    "5. volume": "30",
                },
            }
        },
        symbol="IBM",
        count=2,
    )

    assert symbol == "IBM"
    assert [bar.trading_day for bar in bars] == ["2026-05-21", "2026-05-19"]


def test_required_string_trims_and_rejects_blanks(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    assert plugin._required_string(" IBM ", "symbol") == "IBM"

    with pytest.raises(StockMarketDataPluginError, match="missing symbol"):
        plugin._required_string(" ", "symbol")


def test_required_float_rejects_malformed_values(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(StockMarketDataPluginError, match="invalid price"):
        plugin._required_float("abc", "price")


def test_optional_scalar_helpers_return_none_for_blank_or_missing_values(
    tmp_path: Path,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    assert plugin._optional_float(" ") is None
    assert plugin._optional_float(None) is None
    assert plugin._optional_int(" ") is None
    assert plugin._optional_int(None) is None
    assert plugin._optional_string(" ") is None
    assert plugin._optional_string(None) is None


def test_optional_percentage_strips_percent_and_rejects_malformed_inputs(
    tmp_path: Path,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    assert plugin._optional_percentage(" 3.75% ") == 3.75
    assert plugin._optional_percentage(" ") is None

    with pytest.raises(StockMarketDataPluginError, match="invalid percentage"):
        plugin._optional_percentage("bad%")
