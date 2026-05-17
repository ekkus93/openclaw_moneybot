from __future__ import annotations

from pydantic import BaseModel


class EvidenceArchiveRequest(BaseModel):
    related_type: str
    related_id: str
    evidence_type: str
    source_url: str | None = None
    content_text: str | None = None
    content_bytes_path: str | None = None
    mime_type: str | None = None
    captured_at: str | None = None
    notes: str | None = None


class EvidenceArchiveResult(BaseModel):
    evidence_id: str
    related_type: str
    related_id: str
    evidence_type: str
    archive_path: str | None = None
    metadata_path: str | None = None
    content_sha256: str
    source_url: str | None = None
    created_at: str | None = None
