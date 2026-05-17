"""Base Pydantic model helpers."""

from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator


class MoneyBotModel(BaseModel):
    """Shared base model with strict validation defaults."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)


class TimestampedModel(MoneyBotModel):
    """Base model for records with timestamps."""

    created_at: AwareDatetime

    @field_validator("created_at")
    @classmethod
    def ensure_timezone_aware(cls, value: datetime) -> datetime:
        """Require timezone-aware datetimes."""
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "created_at must be timezone-aware"
            raise ValueError(msg)
        return value
