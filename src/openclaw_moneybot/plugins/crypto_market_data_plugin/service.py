"""Read-only CoinGecko crypto market data integration."""

from __future__ import annotations

import httpx

from openclaw_moneybot.plugins.crypto_market_data_plugin.models import (
    CryptoMarketChartPoint,
    CryptoMarketChartRequest,
    CryptoMarketChartResult,
    CryptoSpotPriceRequest,
    CryptoSpotPriceResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, CryptoMarketDataConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class CryptoMarketDataPluginError(RuntimeError):
    """Raised when crypto market data cannot be retrieved safely."""


class CryptoMarketDataPlugin:
    """Fetch bounded crypto spot-price and market-chart data through CoinGecko."""

    def __init__(
        self,
        config: CryptoMarketDataConfig,
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
        """Return plugin health metadata."""

        return PluginHealthResult(
            plugin_name="crypto_market_data_plugin",
            enabled=self.config.enabled,
            read_only=True,
            status="ok",
        )

    def get_spot_price(self, request: CryptoSpotPriceRequest) -> CryptoSpotPriceResult:
        """Fetch one bounded crypto spot price."""

        self._ensure_enabled()
        lookup_id = make_id("crypto")
        payload = self._query(
            lookup_id=lookup_id,
            event_name="crypto_spot_price_failed",
            path="/simple/price",
            params={
                "ids": request.asset_id,
                "vs_currencies": request.vs_currency,
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
            },
        )
        result = self._normalize_spot_price(
            payload,
            asset_id=request.asset_id,
            vs_currency=request.vs_currency,
        )
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.CRYPTO_MARKET_DATA,
            related_id=lookup_id,
            evidence_type="coingecko_spot_price_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded CoinGecko crypto spot-price response snapshot",
        )
        summary = {
            "provider": "coingecko",
            "asset_id": result["asset_id"],
            "vs_currency": result["vs_currency"],
            "price": result["price"],
            "change_24h_percent": result["change_24h_percent"],
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.CRYPTO_MARKET_DATA,
            related_record_id=lookup_id,
            payload={
                "provider": "coingecko",
                "mode": "spot_price",
                "asset_id": result["asset_id"],
                "vs_currency": result["vs_currency"],
                "price": result["price"],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return CryptoSpotPriceResult(
            lookup_id=lookup_id,
            asset_id=result["asset_id"],
            vs_currency=result["vs_currency"],
            price=result["price"],
            market_cap=result["market_cap"],
            total_volume_24h=result["total_volume_24h"],
            change_24h_percent=result["change_24h_percent"],
            last_updated_at_unix=result["last_updated_at_unix"],
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def get_recent_market_chart(
        self,
        request: CryptoMarketChartRequest,
    ) -> CryptoMarketChartResult:
        """Fetch one bounded recent crypto market chart."""

        self._ensure_enabled()
        if request.count > self.config.max_chart_points:
            msg = "Requested chart point count exceeds the configured maximum."
            raise ValueError(msg)
        lookup_id = make_id("crypto")
        payload = self._query(
            lookup_id=lookup_id,
            event_name="crypto_market_chart_failed",
            path=f"/coins/{request.asset_id}/market_chart",
            params={
                "vs_currency": request.vs_currency,
                "days": request.days,
            },
        )
        points = self._normalize_market_chart(payload, count=request.count)
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.CRYPTO_MARKET_DATA,
            related_id=lookup_id,
            evidence_type="coingecko_market_chart_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded CoinGecko market-chart response snapshot",
        )
        summary = {
            "provider": "coingecko",
            "asset_id": request.asset_id,
            "vs_currency": request.vs_currency,
            "days": request.days,
            "timestamps": [item.timestamp_ms for item in points],
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.CRYPTO_MARKET_DATA,
            related_record_id=lookup_id,
            payload={
                "provider": "coingecko",
                "mode": "market_chart",
                "asset_id": request.asset_id,
                "vs_currency": request.vs_currency,
                "days": request.days,
                "result_count": len(points),
                "timestamps": [item.timestamp_ms for item in points],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return CryptoMarketChartResult(
            lookup_id=lookup_id,
            asset_id=request.asset_id,
            vs_currency=request.vs_currency,
            days=request.days,
            result_count=len(points),
            points=points,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def _ensure_enabled(self) -> None:
        if not self.config.enabled:
            msg = "crypto_market_data_plugin is disabled."
            raise ValueError(msg)

    def _query(
        self,
        *,
        lookup_id: str,
        event_name: str,
        path: str,
        params: dict[str, str | int],
    ) -> dict[str, object]:
        try:
            response = self._client.get(
                f"{self.config.api_base_url.rstrip('/')}{path}",
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(lookup_id, event_name, reason="transport_error")
            msg = "CoinGecko market data is unavailable."
            raise CryptoMarketDataPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            self._record_failure(lookup_id, event_name, reason="invalid_response")
            msg = f"CoinGecko request failed: {error}"
            raise CryptoMarketDataPluginError(msg) from error
        if not isinstance(payload, dict):
            msg = "CoinGecko response must be a JSON object."
            raise CryptoMarketDataPluginError(msg)
        provider_error = self._provider_error_message(payload)
        if provider_error is not None:
            self._record_failure(
                lookup_id,
                event_name,
                reason="provider_error",
                provider_error=provider_error,
            )
            msg = f"CoinGecko request failed: {provider_error}"
            raise CryptoMarketDataPluginError(msg)
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
        direct_error = payload.get("error")
        if isinstance(direct_error, str) and direct_error.strip():
            return direct_error.strip()
        status = payload.get("status")
        if isinstance(status, dict):
            error_message = status.get("error_message")
            if isinstance(error_message, str) and error_message.strip():
                return error_message.strip()
        return None

    def _normalize_spot_price(
        self,
        payload: dict[str, object],
        *,
        asset_id: str,
        vs_currency: str,
    ) -> dict[str, str | float | int | None]:
        raw_asset = payload.get(asset_id)
        if not isinstance(raw_asset, dict):
            msg = "CoinGecko spot-price response is missing the requested asset."
            raise CryptoMarketDataPluginError(msg)
        price = self._required_float(raw_asset.get(vs_currency), "price")
        return {
            "asset_id": asset_id,
            "vs_currency": vs_currency,
            "price": price,
            "market_cap": self._optional_float(raw_asset.get(f"{vs_currency}_market_cap")),
            "total_volume_24h": self._optional_float(raw_asset.get(f"{vs_currency}_24h_vol")),
            "change_24h_percent": self._optional_float(
                raw_asset.get(f"{vs_currency}_24h_change")
            ),
            "last_updated_at_unix": self._optional_int(raw_asset.get("last_updated_at")),
        }

    def _normalize_market_chart(
        self,
        payload: dict[str, object],
        *,
        count: int,
    ) -> list[CryptoMarketChartPoint]:
        raw_prices = self._series_points(payload.get("prices"), "prices")
        raw_market_caps = self._series_points(payload.get("market_caps"), "market_caps")
        raw_total_volumes = self._series_points(payload.get("total_volumes"), "total_volumes")

        market_cap_by_timestamp = {timestamp: value for timestamp, value in raw_market_caps}
        total_volume_by_timestamp = {timestamp: value for timestamp, value in raw_total_volumes}

        points = [
            CryptoMarketChartPoint(
                timestamp_ms=timestamp,
                price=price,
                market_cap=market_cap_by_timestamp.get(timestamp),
                total_volume=total_volume_by_timestamp.get(timestamp),
            )
            for timestamp, price in raw_prices[-count:]
        ]
        if not points:
            msg = "CoinGecko market-chart response did not contain any points."
            raise CryptoMarketDataPluginError(msg)
        return points

    def _series_points(
        self,
        value: object,
        field_name: str,
    ) -> list[tuple[int, float]]:
        if not isinstance(value, list):
            msg = f"CoinGecko response is missing {field_name}."
            raise CryptoMarketDataPluginError(msg)
        points: list[tuple[int, float]] = []
        for item in value:
            if not isinstance(item, list) or len(item) != 2:
                continue
            timestamp, numeric_value = item
            if not isinstance(timestamp, int | float) or not isinstance(
                numeric_value, int | float
            ):
                continue
            points.append((int(timestamp), float(numeric_value)))
        return points

    @staticmethod
    def _required_float(value: object, field_name: str) -> float:
        if not isinstance(value, int | float):
            msg = f"CoinGecko response is missing {field_name}."
            raise CryptoMarketDataPluginError(msg)
        return float(value)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if not isinstance(value, int | float):
            return None
        return float(value)

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if not isinstance(value, int | float):
            return None
        return int(value)
