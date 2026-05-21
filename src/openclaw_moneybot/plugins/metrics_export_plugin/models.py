"""Models for deterministic metrics exports."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, JsonValue

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import ExportJobStatus


class MetricsExportRequest(MoneyBotModel):
    """Request for one approved metrics export."""

    export_type: str
    output_format: str = "json"
    start_day: str | None = None
    end_day: str | None = None
    opportunity_category: str | None = None
    outcome_category: str | None = None
    limit: int = Field(default=100, gt=0)


class MetricsExportResult(MoneyBotModel):
    """Result for one bounded metrics export."""

    export_job_id: str
    status: ExportJobStatus
    output_path: Path
    row_count: int = Field(ge=0)
    summary: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
