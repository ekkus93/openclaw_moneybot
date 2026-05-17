"""HTTP client wrapper for the wallet governor service."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import JsonValue

from openclaw_moneybot.shared import WalletGovernorConfig


class WalletGovernorClientError(RuntimeError):
    """Raised when the wallet governor service cannot be reached safely."""


class WalletGovernorHttpClient:
    """Local-only HTTP client for wallet-governor operations."""

    def __init__(
        self,
        config: WalletGovernorConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def health(self) -> dict[str, JsonValue]:
        return self._request_json("GET", "/health", retryable=True)

    def balance(self, asset: str) -> dict[str, JsonValue]:
        return self._request_json("GET", "/balance", params={"asset": asset}, retryable=True)

    def limits(self, asset: str) -> dict[str, JsonValue]:
        return self._request_json("GET", "/limits", params={"asset": asset}, retryable=True)

    def quote_spend(self, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return self._request_json("POST", "/quote-spend", json_payload=payload, retryable=True)

    def send_small_payment(self, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return self._request_json("POST", "/send-small-payment", json_payload=payload)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, JsonValue] | None = None,
        retryable: bool = False,
    ) -> dict[str, JsonValue]:
        attempts = 2 if retryable else 1
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    json=json_payload,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "wallet governor response must be a JSON object"
                    raise WalletGovernorClientError(msg)
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as error:
                last_error = error
            except (httpx.HTTPStatusError, ValueError) as error:
                msg = f"wallet governor request failed: {error}"
                raise WalletGovernorClientError(msg) from error
        msg = "wallet governor unavailable"
        raise WalletGovernorClientError(msg) from last_error
