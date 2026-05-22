"""Unit tests for the crypto market data plugin."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from openclaw_moneybot.plugins.crypto_market_data_plugin import (
    CryptoMarketChartRequest,
    CryptoMarketDataPlugin,
    CryptoMarketDataPluginError,
    CryptoSpotPriceRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, CryptoMarketDataConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(
    tmp_path: Path,
    *,
    enabled: bool = True,
    handler: httpx.BaseTransport | None = None,
) -> tuple[CryptoMarketDataPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = CryptoMarketDataPlugin(
        CryptoMarketDataConfig(
            enabled=enabled,
            max_chart_points=10,
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def test_get_spot_price_returns_normalized_result(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.coingecko.com"
        assert request.url.path == "/api/v3/simple/price"
        assert request.url.params["ids"] == "bitcoin"
        assert request.url.params["vs_currencies"] == "usd"
        return httpx.Response(
            200,
            json={
                "bitcoin": {
                    "usd": 70000.5,
                    "usd_market_cap": 1380000000000.0,
                    "usd_24h_vol": 25000000000.0,
                    "usd_24h_change": 2.5,
                    "last_updated_at": 1711983682,
                }
            },
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.get_spot_price(CryptoSpotPriceRequest(asset_id="Bitcoin"))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.CRYPTO_MARKET_DATA,
        related_id=result.lookup_id,
    )

    assert result.asset_id == "bitcoin"
    assert result.vs_currency == "usd"
    assert result.price == 70000.5
    assert result.change_24h_percent == 2.5
    assert result.last_updated_at_unix == 1711983682
    assert evidence[0].evidence_type == "coingecko_spot_price_response"


def test_get_recent_market_chart_returns_bounded_points(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/coins/bitcoin/market_chart"
        assert request.url.params["days"] == "7"
        return httpx.Response(
            200,
            json={
                "prices": [
                    [1711843200000, 69702.3],
                    [1711929600000, 71246.9],
                    [1711983682000, 68887.7],
                ],
                "market_caps": [
                    [1711843200000, 1370247487960.09],
                    [1711929600000, 1401370211582.37],
                    [1711983682000, 1355701979725.16],
                ],
                "total_volumes": [
                    [1711843200000, 16408802301.83],
                    [1711929600000, 19723005998.21],
                    [1711983682000, 30137418199.64],
                ],
            },
        )

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.get_recent_market_chart(
        CryptoMarketChartRequest(asset_id="bitcoin", days=7, count=2)
    )

    assert result.asset_id == "bitcoin"
    assert result.result_count == 2
    assert result.points[0].timestamp_ms == 1711929600000
    assert result.points[1].total_volume == 30137418199.64


def test_get_spot_price_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.get_spot_price(CryptoSpotPriceRequest(asset_id="bitcoin"))


def test_get_recent_market_chart_rejects_provider_error_payload(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": {"error_message": "rate limit exceeded"}})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(CryptoMarketDataPluginError, match="rate limit exceeded"):
        plugin.get_recent_market_chart(
            CryptoMarketChartRequest(asset_id="bitcoin", days=7, count=2)
        )


def test_get_recent_market_chart_rejects_malformed_payloads(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"prices": []})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(CryptoMarketDataPluginError, match="market_caps"):
        plugin.get_recent_market_chart(
            CryptoMarketChartRequest(asset_id="bitcoin", days=7, count=2)
        )


def test_get_spot_price_surfaces_transport_failures_as_plugin_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(CryptoMarketDataPluginError, match="unavailable"):
        plugin.get_spot_price(CryptoSpotPriceRequest(asset_id="bitcoin"))
