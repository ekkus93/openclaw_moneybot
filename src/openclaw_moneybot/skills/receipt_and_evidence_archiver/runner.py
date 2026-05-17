"""Evidence archiver entrypoint."""

from __future__ import annotations

from openclaw_moneybot.shared import ArchiveConfig, EvidenceRecord
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver.models import (
    EvidenceArchiveRequest,
    EvidenceArchiveResult,
)
from openclaw_moneybot.skills.receipt_and_evidence_archiver.storage import (
    normalize_evidence_type,
    store_artifact,
)
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class ReceiptAndEvidenceArchiver:
    """Archive evidence locally and write it to the ledger."""

    def __init__(self, config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.config = config
        self.ledger_service = ledger_service

    def archive(self, request: EvidenceArchiveRequest) -> EvidenceArchiveResult:
        """Archive evidence content and create a ledger record."""
        created_at = (
            request.captured_at
            if request.captured_at is not None
            else utc_now().isoformat(timespec="seconds")
        )
        evidence_id = make_id("artifact")
        (
            archive_path,
            metadata_path,
            content_sha256,
            file_size,
            redactions,
        ) = store_artifact(
            self.config,
            request,
            evidence_id=evidence_id,
            captured_at=created_at,
        )
        ledger_record = EvidenceRecord(
            created_at=utc_now(),
            evidence_id=evidence_id,
            related_record_type=request.related_type,
            related_record_id=request.related_id,
            evidence_type=normalize_evidence_type(request.evidence_type),
            archive_path=str(archive_path),
            content_sha256=content_sha256,
            source_url=request.final_url or request.source_url,
            metadata={
                "metadata_path": str(metadata_path),
                "notes": request.notes,
                "page_title": request.page_title,
                "redactions": redactions,
                "summary_hint": request.summary_hint,
            },
        )
        self.ledger_service.record_evidence(
            ledger_record, idempotency_key=f"evidence:{ledger_record.evidence_id}"
        )
        return EvidenceArchiveResult(
            evidence_id=evidence_id,
            related_type=request.related_type,
            related_id=request.related_id,
            evidence_type=normalize_evidence_type(request.evidence_type),
            archive_path=archive_path,
            metadata_path=metadata_path,
            content_sha256=content_sha256,
            source_url=request.final_url or request.source_url,
            created_at=created_at,
            ledger_record=ledger_record,
            file_size=file_size,
            redactions=redactions,
        )
