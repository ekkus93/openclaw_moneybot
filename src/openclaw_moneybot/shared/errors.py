"""Structured error types."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, JsonValue

from openclaw_moneybot.shared.base import MoneyBotModel


class ErrorCode(StrEnum):
    """Stable application error codes."""

    VALIDATION_ERROR = "validation_error"
    MISSING_CONFIG = "missing_config"
    INVALID_CONFIG = "invalid_config"
    LEDGER_ERROR = "ledger_error"
    POLICY_BLOCKED = "policy_blocked"
    NEEDS_REVIEW = "needs_review"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    STORAGE_ERROR = "storage_error"
    WALLET_ERROR = "wallet_error"


class MoneyBotErrorDetail(MoneyBotModel):
    """Structured error payload."""

    error_code: ErrorCode
    message: str
    recoverable: bool
    safe_for_user: bool
    details: dict[str, JsonValue] = Field(default_factory=dict)


class MoneyBotError(Exception):
    """Exception wrapper that carries a structured error detail."""

    def __init__(self, detail: MoneyBotErrorDetail) -> None:
        super().__init__(detail.message)
        self.detail = detail

    def to_model(self) -> MoneyBotErrorDetail:
        """Return the structured error detail."""
        return self.detail
