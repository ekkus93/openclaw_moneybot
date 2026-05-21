"""Models for deadline scheduling and summaries."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import DeadlineState


class DeadlineScheduleRequest(MoneyBotModel):
    """Add or update one deadline item."""

    reference_id: str
    deadline_text: str | None = None
    deadline_at: datetime | None = None
    current_time: datetime
    provenance: str | None = None
    source_evidence_ids: list[str] = Field(default_factory=list)
    cooldown_until: datetime | None = None
    retry_after: datetime | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> DeadlineScheduleRequest:
        if self.deadline_text is None and self.deadline_at is None:
            msg = "Either deadline_text or deadline_at is required."
            raise ValueError(msg)
        return self


class DeadlineScheduleResult(MoneyBotModel):
    """Stored deadline item result."""

    deadline_event_id: str
    state: DeadlineState
    deadline_at: datetime | None = None
    confidence: str
    uncertainty_reason: str | None = None
    source_evidence_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord


class DeadlineQueryRequest(MoneyBotModel):
    """Summary query for upcoming and overdue items."""

    current_time: datetime
    upcoming_within_hours: int = Field(default=72, ge=1)


class DeadlineQueryResult(MoneyBotModel):
    """Deterministic deadline summary output."""

    summary_id: str
    upcoming_reference_ids: list[str] = Field(default_factory=list)
    overdue_reference_ids: list[str] = Field(default_factory=list)
    uncertain_reference_ids: list[str] = Field(default_factory=list)
    conflicting_reference_ids: list[str] = Field(default_factory=list)
    cooling_down_reference_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
