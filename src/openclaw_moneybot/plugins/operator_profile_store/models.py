"""Models for local operator-profile storage."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, JsonValue

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import ProfileAttributeAvailability
from openclaw_moneybot.skills.account_eligibility_checker import OperatorProfile


class OperatorProfileStoreWriteRequest(MoneyBotModel):
    """Typed write request for the operator profile store."""

    fields: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str


class OperatorProfileStoreWriteResult(MoneyBotModel):
    """Result of writing profile data."""

    profile_version: int = Field(ge=1)
    last_updated: datetime
    stored_profile: OperatorProfile
    ledger_record: LedgerRecord
    audit_record_id: str
    redacted_export: dict[str, JsonValue] = Field(default_factory=dict)


class OperatorProfileStoreReadRequest(MoneyBotModel):
    """Read request for a subset of operator-profile fields."""

    field_names: list[str] = Field(default_factory=list)


class OperatorProfileFieldResult(MoneyBotModel):
    """Per-field read result with safe availability semantics."""

    availability: ProfileAttributeAvailability
    value: JsonValue | None = None
    provenance: str | None = None
    updated_at: datetime | None = None


class OperatorProfileStoreReadResult(MoneyBotModel):
    """Read result for profile field queries."""

    profile_version: int = Field(ge=0)
    last_updated: datetime | None = None
    stored_profile: OperatorProfile
    field_results: dict[str, OperatorProfileFieldResult] = Field(default_factory=dict)
    redacted_export: dict[str, JsonValue] = Field(default_factory=dict)
