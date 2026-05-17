from __future__ import annotations

import tempfile

from skills.receipt_and_evidence_archiver.models import EvidenceArchiveRequest
from skills.receipt_and_evidence_archiver.runner import archive_evidence


def test_archive_evidence_text() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        req = EvidenceArchiveRequest(
            related_type="opportunity",
            related_id="opp-1",
            evidence_type="source_page",
            content_text="test content",
            source_url="https://example.com",
        )
        result = archive_evidence(req, base_path=tmp)
        assert result.evidence_id.startswith("source_page_")
        assert result.content_sha256 is not None


def test_archive_returns_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        req = EvidenceArchiveRequest(
            related_type="opportunity",
            related_id="opp-2",
            evidence_type="tos_page",
            content_text="TOS text",
        )
        result = archive_evidence(req, base_path=tmp)
        assert result.archive_path is not None
        assert result.metadata_path is not None
