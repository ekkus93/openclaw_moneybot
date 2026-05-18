"""Models for evidence archival."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, HttpUrl, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import EvidenceRecord
from openclaw_moneybot.shared.types import RecordType


class EvidenceArchiveRequest(MoneyBotModel):
    """Request for archiving a local or generated artifact."""

    related_type: RecordType
    related_id: str
    evidence_type: str
    source_url: HttpUrl | None = None
    content_text: str | None = None
    content_bytes_path: Path | None = None
    mime_type: str | None = None
    captured_at: str | None = None
    notes: str = ""
    summary_hint: str | None = None
    final_url: HttpUrl | None = None
    page_title: str | None = None

    @model_validator(mode="after")
    def validate_content_source(self) -> EvidenceArchiveRequest:
        """Require a content source."""
        if self.content_text is None and self.content_bytes_path is None:
            msg = "Either content_text or content_bytes_path is required."
            raise ValueError(msg)
        if self.content_bytes_path is not None and "\x00" in str(self.content_bytes_path):
            msg = "Unsafe content_bytes_path is not allowed."
            raise ValueError(msg)
        return self


class EvidenceArchiveResult(MoneyBotModel):
    """Result of an archival operation."""

    evidence_id: str
    related_type: RecordType
    related_id: str
    evidence_type: str
    archive_path: Path
    metadata_path: Path
    content_sha256: str
    source_url: HttpUrl | None = None
    created_at: str
    ledger_record: EvidenceRecord
    storage_version: int = 1
    file_size: int = Field(ge=0)
    redactions: list[str] = Field(default_factory=list)
