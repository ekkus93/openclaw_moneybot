from __future__ import annotations

from skills.receipt_and_evidence_archiver.models import (
    EvidenceArchiveRequest,
    EvidenceArchiveResult,
)
from skills.receipt_and_evidence_archiver.storage import (
    create_archive_file,
    ensure_archive_dir,
)


def archive_evidence(
    req: EvidenceArchiveRequest,
    base_path: str,
) -> EvidenceArchiveResult:
    ensure_archive_dir(base_path)
    evidence_id = req.evidence_type + "_" + req.related_id

    if req.content_text is not None:
        content = req.content_text.encode("utf-8")
    elif req.content_bytes_path is not None:
        with open(req.content_bytes_path, "rb") as f:
            content = f.read()
    else:
        content = b""

    file_path, meta_path = create_archive_file(
        base_path,
        evidence_id,
        req.related_id,
        content,
    )

    from skills.receipt_and_evidence_archiver.hashing import sha256_of_bytes

    sha = sha256_of_bytes(content)

    return EvidenceArchiveResult(
        evidence_id=evidence_id,
        related_type=req.related_type,
        related_id=req.related_id,
        evidence_type=req.evidence_type,
        archive_path=file_path,
        metadata_path=meta_path,
        content_sha256=sha,
        source_url=req.source_url,
        created_at=req.captured_at,
    )
