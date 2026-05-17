"""Ledger skill models."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.types import RecordType


class LedgerWriteResult(MoneyBotModel):
    """Result of a ledger write operation."""

    record_id: str
    ledger_event_id: str
    ledger_write_confirmed: bool = True
    reused_existing_event: bool = False


class LedgerTimelineEntry(MoneyBotModel):
    """An item in the opportunity timeline."""

    created_at: str
    event_type: str
    related_type: RecordType
    related_id: str


class TaxExportResult(MoneyBotModel):
    """Result of exporting ledger tax/accounting data."""

    output_path: Path
    row_count: int = Field(ge=0)
