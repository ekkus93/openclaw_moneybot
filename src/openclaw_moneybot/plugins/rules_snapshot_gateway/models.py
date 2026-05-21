"""Models for rules snapshot capture and diffing."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, HttpUrl

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import SnapshotFreshness


class RulesSnapshotCaptureRequest(MoneyBotModel):
    """Typed request for capturing one rules snapshot."""

    opportunity_id: str
    source_url: HttpUrl
    content_text: str = Field(min_length=1)
    content_type: str
    idempotency_key: str


class RulesSnapshotCaptureResult(MoneyBotModel):
    """Capture result with hashes, diff metadata, and archive linkage."""

    snapshot_record_id: str
    capture_time: datetime
    normalized_hash: str
    raw_hash: str
    previous_snapshot_record_id: str | None = None
    change_detected: bool = False
    diff_text: str = ""
    freshness: SnapshotFreshness = SnapshotFreshness.UNKNOWN
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
