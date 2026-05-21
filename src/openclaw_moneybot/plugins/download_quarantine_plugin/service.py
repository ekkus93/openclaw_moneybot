"""Stage untrusted files in a bounded quarantine pipeline."""

from __future__ import annotations

import io
import json
import zipfile
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

from openclaw_moneybot.plugins.download_quarantine_plugin.models import (
    QuarantineIngestRequest,
    QuarantineIngestResult,
    QuarantinePromoteRequest,
    QuarantinePromoteResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, DownloadQuarantineConfig
from openclaw_moneybot.shared.types import QuarantineScanStatus, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import record_structured_result
from openclaw_moneybot.utils.ids import make_id

EXECUTABLE_SIGNATURES = (b"MZ", b"\x7fELF", b"#!")


class DownloadQuarantinePlugin:
    """Safely stage downloads and attachments before trust is granted."""

    def __init__(
        self,
        config: DownloadQuarantineConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
    ) -> None:
        self.config = config
        archive_allowed_roots = [*archive_config.allowed_source_roots, config.quarantine_root]
        self.archiver = ReceiptAndEvidenceArchiver(
            archive_config.model_copy(update={"allowed_source_roots": archive_allowed_roots}),
            ledger_service,
        )
        self.ledger_service = ledger_service

    def health(self) -> PluginHealthResult:
        return PluginHealthResult(
            plugin_name="download_quarantine_plugin",
            enabled=self.config.enabled,
            read_only=False,
        )

    def ingest(self, request: QuarantineIngestRequest) -> QuarantineIngestResult:
        """Stage one untrusted file in quarantine."""

        scan_id = make_id("quarantine_scan")
        safe_name = self._safe_name(request.file_name)
        extension = Path(safe_name).suffix.lower()
        host = (
            None
            if request.source_url is None
            else (urlparse(request.source_url).hostname or "").lower()
        )
        rejection_reason = self._validate_file(
            safe_name=safe_name,
            extension=extension,
            mime_type=request.mime_type.lower(),
            content_bytes=request.content_bytes,
            host=host,
        )
        if rejection_reason is not None:
            record_plugin_audit_event(
                self.ledger_service,
                related_record_id=request.related_record_id,
                event_name="quarantine_ingest_rejected",
                payload={"file_name": safe_name, "reason": rejection_reason},
            )
            ledger_record = record_structured_result(
                self.ledger_service,
                record_id=scan_id,
                record_type=RecordType.QUARANTINE_SCAN,
                related_record_id=request.related_record_id,
                payload={"status": QuarantineScanStatus.REJECTED.value, "reason": rejection_reason},
            )
            return QuarantineIngestResult(
                scan_id=scan_id,
                status=QuarantineScanStatus.REJECTED,
                reason=rejection_reason,
                ledger_record=ledger_record,
            )

        quarantine_dir = (self.config.quarantine_root / scan_id).resolve()
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        staged_path = quarantine_dir / safe_name
        staged_path.write_bytes(request.content_bytes)
        content_sha256 = sha256(request.content_bytes).hexdigest()
        metadata_path = quarantine_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "scan_id": scan_id,
                    "file_name": safe_name,
                    "mime_type": request.mime_type.lower(),
                    "source_url": request.source_url,
                    "status": QuarantineScanStatus.STAGED.value,
                    "content_sha256": content_sha256,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=scan_id,
            record_type=RecordType.QUARANTINE_SCAN,
            related_record_id=request.related_record_id,
            payload={
                "status": QuarantineScanStatus.STAGED.value,
                "file_name": safe_name,
                "mime_type": request.mime_type.lower(),
                "content_sha256": content_sha256,
                "staged_path": str(staged_path),
            },
        )
        return QuarantineIngestResult(
            scan_id=scan_id,
            status=QuarantineScanStatus.STAGED,
            staged_path=staged_path,
            content_sha256=content_sha256,
            ledger_record=ledger_record,
        )

    def promote(self, request: QuarantinePromoteRequest) -> QuarantinePromoteResult:
        """Promote a staged file into the evidence archive."""

        staged_dir = (self.config.quarantine_root / request.scan_id).resolve()
        metadata_path = staged_dir / "metadata.json"
        if not metadata_path.exists():
            msg = "Unknown quarantine scan."
            raise ValueError(msg)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("status") != QuarantineScanStatus.STAGED.value:
            msg = "Only staged files may be promoted."
            raise ValueError(msg)
        file_name = str(metadata["file_name"])
        staged_path = staged_dir / file_name
        archived = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=request.related_type,
                related_id=request.related_id,
                evidence_type=request.evidence_type,
                content_bytes_path=staged_path,
                notes="Promoted from download quarantine",
            )
        )
        metadata["status"] = QuarantineScanStatus.PROMOTED.value
        metadata["promoted_evidence_id"] = archived.evidence_id
        metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=request.scan_id,
            record_type=RecordType.QUARANTINE_SCAN,
            related_record_id=request.related_id,
            payload={
                "status": QuarantineScanStatus.PROMOTED.value,
                "promoted_evidence_id": archived.evidence_id,
                "file_name": file_name,
            },
        )
        return QuarantinePromoteResult(
            scan_id=request.scan_id,
            status=QuarantineScanStatus.PROMOTED,
            promoted_evidence_id=archived.evidence_id,
            ledger_record=ledger_record,
        )

    def _validate_file(
        self,
        *,
        safe_name: str,
        extension: str,
        mime_type: str,
        content_bytes: bytes,
        host: str | None,
    ) -> str | None:
        if host is not None and host not in self.config.allowed_hosts:
            return "host_not_allowlisted"
        if extension not in self.config.allowed_extensions:
            return "extension_not_allowed"
        if mime_type not in self.config.allowed_mime_types:
            return "mime_type_not_allowed"
        if len(content_bytes) > self.config.max_file_bytes:
            return "file_too_large"
        if content_bytes.startswith(EXECUTABLE_SIGNATURES):
            return "executable_content_blocked"
        if extension == ".zip":
            return self._validate_zip(content_bytes)
        return None

    def _validate_zip(self, content_bytes: bytes) -> str | None:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as archive:
            entries = archive.infolist()
            if len(entries) > self.config.max_archive_entries:
                return "zip_entry_count_exceeded"
            total_uncompressed = sum(item.file_size for item in entries)
            if total_uncompressed > self.config.max_nested_bytes:
                return "zip_nested_size_exceeded"
            for item in entries:
                if Path(item.filename).is_absolute() or ".." in Path(item.filename).parts:
                    return "zip_path_traversal"
        return None

    @staticmethod
    def _safe_name(file_name: str) -> str:
        path = Path(file_name)
        if path.is_absolute() or ".." in path.parts:
            msg = "Quarantine file path must stay within the quarantine root."
            raise ValueError(msg)
        return path.name
