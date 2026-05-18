"""Local-only HTTP wrapper for the wallet governor service."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from openclaw_moneybot.plugins.wallet_governor_service.backend import WalletBackendError
from openclaw_moneybot.plugins.wallet_governor_service.service import (
    ALLOWED_SPEND_CATEGORIES,
    BLOCKED_SPEND_CATEGORIES,
    WalletGovernorService,
)

LOCAL_BIND_HOSTS = {"127.0.0.1", "localhost"}


def create_wallet_governor_app(
    service: WalletGovernorService,
    *,
    bind_host: str = "127.0.0.1",
    service_version: str = "0.1.0",
    max_request_bytes: int = 16_384,
    request_timeout_seconds: float | None = None,
) -> FastAPI:
    """Create a local-only ASGI app for the wallet governor service."""
    if bind_host not in LOCAL_BIND_HOSTS:
        msg = "Wallet governor HTTP service must bind to localhost or 127.0.0.1."
        raise ValueError(msg)

    timeout_seconds = request_timeout_seconds or service.config.timeout_seconds
    app = FastAPI(title="OpenClaw MoneyBot Wallet Governor", version=service_version)
    app.state.bind_host = bind_host
    app.state.max_request_bytes = max_request_bytes
    app.state.request_timeout_seconds = timeout_seconds

    @app.middleware("http")
    async def enforce_body_size_limit(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > max_request_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "request body too large"},
            )
        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout_seconds)
        except TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"detail": "request timed out"},
            )

    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        del request
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(WalletBackendError)
    async def handle_backend_error(
        request: Request,
        exc: WalletBackendError,
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def handle_validation_error(
        request: Request,
        exc: ValidationError,
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.get("/health")
    def health() -> dict[str, object]:
        payload = service.health().model_dump(mode="json")
        payload["version"] = service_version
        payload["backend_mode"] = payload["backend"]
        return payload

    @app.get("/balance")
    def balance(asset: str = "BTC") -> dict[str, object]:
        payload = service.balance(asset).model_dump(mode="json")
        payload["spend_enabled"] = service.config.spend_enabled
        payload["network"] = "local"
        return payload

    @app.get("/limits")
    def limits(asset: str = "BTC") -> dict[str, object]:
        payload = service.limits(asset).model_dump(mode="json")
        payload["allowed_categories"] = sorted(ALLOWED_SPEND_CATEGORIES)
        payload["blocked_categories"] = sorted(BLOCKED_SPEND_CATEGORIES)
        return payload

    @app.post("/quote-spend")
    def quote(request: dict[str, object]) -> dict[str, object]:
        return service.quote_json(request)

    @app.post("/send-small-payment")
    def send_small_payment(request: dict[str, object]) -> dict[str, object]:
        return service.capped_send_json(request)

    return app
