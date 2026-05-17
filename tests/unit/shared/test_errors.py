"""Tests for structured errors."""

from __future__ import annotations

from openclaw_moneybot.shared.errors import ErrorCode, MoneyBotError, MoneyBotErrorDetail


def test_moneybot_error_preserves_structured_detail() -> None:
    """Exceptions keep the structured payload intact."""
    detail = MoneyBotErrorDetail(
        error_code=ErrorCode.VALIDATION_ERROR,
        message="Invalid test payload",
        recoverable=True,
        safe_for_user=True,
        details={"field": "category"},
    )

    error = MoneyBotError(detail)

    assert error.to_model() == detail
    assert str(error) == "Invalid test payload"
