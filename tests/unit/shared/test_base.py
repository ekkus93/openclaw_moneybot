"""Tests for shared base models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from openclaw_moneybot.shared.base import TimestampedModel


class ExampleTimestampedModel(TimestampedModel):
    value: str


def test_timestamped_model_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="timezone_aware|timezone info"):
        ExampleTimestampedModel.model_validate(
            {
                "created_at": datetime(2026, 1, 1, 0, 0, 0),
                "value": "example",
            }
        )
