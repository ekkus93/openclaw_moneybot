"""Models for quarantine ingest and promotion."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import QuarantineScanStatus, RecordType


class QuarantineIngestRequest(MoneyBotModel):
    """Ingest request for downloads or attachments."""

    related_record_id: str
    file_name: str
    content_bytes: bytes
    mime_type: str
    source_url: str | None = None
    source_kind: str = "download"


class QuarantineIngestResult(MoneyBotModel):
    """Result of staging one quarantined file."""

    scan_id: str
    status: QuarantineScanStatus
    staged_path: Path | None = None
    content_sha256: str | None = None
    reason: str | None = None
    ledger_record: LedgerRecord


class QuarantinePromoteRequest(MoneyBotModel):
    """Promotion request from quarantine into archived evidence."""

    scan_id: str
    related_type: RecordType
    related_id: str
    evidence_type: str


class QuarantinePromoteResult(MoneyBotModel):
    """Promotion result for one quarantined file."""

    scan_id: str
    status: QuarantineScanStatus
    promoted_evidence_id: str | None = None
    ledger_record: LedgerRecord
