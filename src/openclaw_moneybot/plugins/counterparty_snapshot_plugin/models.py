"""Models for public counterparty snapshot capture."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, JsonValue

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import CounterpartyEvidenceTier, SnapshotFreshness


class CounterpartySnapshotRequest(MoneyBotModel):
    """Request for capturing one public counterparty snapshot."""

    opportunity_id: str
    counterparty_name: str
    source_url: str
    source_category: str
    content_type: str = "text/plain"
    content_text: str
    captured_at: datetime
    current_time: datetime | None = None
    expected_fields: list[str] = Field(
        default_factory=lambda: [
            "display_name",
            "support_email",
            "payout_terms_present",
            "payment_proof_present",
        ]
    )


class CounterpartySnapshotResult(MoneyBotModel):
    """Structured result for a public counterparty snapshot."""

    snapshot_id: str
    source_category: str
    source_url: str
    captured_at: datetime
    freshness: SnapshotFreshness
    evidence_tier: CounterpartyEvidenceTier
    indicators: dict[str, JsonValue] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    changed_fields: list[str] = Field(default_factory=list)
    previous_snapshot_id: str | None = None
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
