"""Capture and diff allowlisted rule snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta
from difflib import unified_diff
from hashlib import sha256
from urllib.parse import urlparse

from openclaw_moneybot.plugins.rules_snapshot_gateway.models import (
    RulesSnapshotCaptureRequest,
    RulesSnapshotCaptureResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, RulesSnapshotGatewayConfig
from openclaw_moneybot.shared.types import RecordType, SnapshotFreshness
from openclaw_moneybot.skills.ledger_skill.models import LedgerEventEntry
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import record_structured_result
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class RulesSnapshotGateway:
    """Version and diff rule snapshots from allowlisted sources."""

    def __init__(
        self,
        config: RulesSnapshotGatewayConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
    ) -> None:
        self.config = config
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def health(self) -> PluginHealthResult:
        """Return health metadata for the local gateway."""

        return PluginHealthResult(
            plugin_name="rules_snapshot_gateway",
            enabled=self.config.enabled,
            read_only=True,
        )

    def capture(self, request: RulesSnapshotCaptureRequest) -> RulesSnapshotCaptureResult:
        """Capture, normalize, hash, and diff one rules snapshot."""

        host = (urlparse(str(request.source_url)).hostname or "").lower()
        if host not in self.config.allowed_hosts:
            self._record_failure(request.opportunity_id, "host_not_allowlisted", host=host)
            msg = "Rules snapshot source host is not allowlisted."
            raise ValueError(msg)
        if request.content_type.lower() not in self.config.allowed_content_types:
            self._record_failure(
                request.opportunity_id,
                "unsupported_content_type",
                content_type=request.content_type,
            )
            msg = "Rules snapshot content type is not supported."
            raise ValueError(msg)
        raw_bytes = request.content_text.encode("utf-8")
        if len(raw_bytes) > self.config.max_content_bytes:
            self._record_failure(
                request.opportunity_id,
                "snapshot_too_large",
                content_bytes=len(raw_bytes),
            )
            msg = "Rules snapshot content exceeds the configured size limit."
            raise ValueError(msg)

        capture_time = utc_now()
        snapshot_record_id = make_id("rule_snapshot")
        normalized_text = self._normalize(request.content_text)
        raw_hash = sha256(raw_bytes).hexdigest()
        normalized_hash = sha256(normalized_text.encode("utf-8")).hexdigest()
        previous = self._find_previous_snapshot(request.opportunity_id, str(request.source_url))
        previous_payload = previous.payload.get("payload") if previous is not None else None
        previous_normalized = ""
        previous_snapshot_record_id: str | None = None
        freshness = SnapshotFreshness.UNKNOWN
        if isinstance(previous_payload, dict):
            assert previous is not None
            previous_record_id = previous.payload.get("record_id")
            if isinstance(previous_record_id, str):
                previous_snapshot_record_id = previous_record_id
            previous_normalized = str(previous_payload.get("normalized_text", ""))
            previous_created = str(previous_payload.get("captured_at", previous.created_at))
            freshness = self._freshness(previous_created)
        diff_text = "\n".join(
            unified_diff(
                previous_normalized.splitlines(),
                normalized_text.splitlines(),
                fromfile="previous",
                tofile="current",
                lineterm="",
            )
        )
        change_detected = normalized_text != previous_normalized if previous is not None else False

        raw_evidence = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.RULE_SNAPSHOT,
                related_id=snapshot_record_id,
                evidence_type="rules_snapshot_raw",
                content_text=request.content_text,
                source_url=request.source_url,
                notes="Raw rules snapshot capture.",
            )
        )
        normalized_evidence = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.RULE_SNAPSHOT,
                related_id=snapshot_record_id,
                evidence_type="rules_snapshot_normalized",
                content_text=normalized_text,
                source_url=request.source_url,
                notes="Normalized rules snapshot capture.",
            )
        )
        evidence_archive_ids = [raw_evidence.evidence_id, normalized_evidence.evidence_id]
        if diff_text:
            diff_evidence = self.archiver.archive(
                EvidenceArchiveRequest(
                    related_type=RecordType.RULE_SNAPSHOT,
                    related_id=snapshot_record_id,
                    evidence_type="rules_snapshot_diff",
                    content_text=diff_text,
                    source_url=request.source_url,
                    notes="Stable diff between rule snapshots.",
                )
            )
            evidence_archive_ids.append(diff_evidence.evidence_id)

        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=snapshot_record_id,
            record_type=RecordType.RULE_SNAPSHOT,
            related_record_id=request.opportunity_id,
            payload={
                "opportunity_id": request.opportunity_id,
                "source_url": str(request.source_url),
                "content_type": request.content_type.lower(),
                "captured_at": capture_time.isoformat(),
                "raw_hash": raw_hash,
                "normalized_hash": normalized_hash,
                "normalized_text": normalized_text,
                "previous_snapshot_record_id": previous_snapshot_record_id,
                "change_detected": change_detected,
                "diff_text": diff_text,
                "freshness": freshness.value,
                "evidence_archive_ids": evidence_archive_ids,
            },
        )
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=snapshot_record_id,
            event_name="rules_snapshot_capture",
            payload={
                "opportunity_id": request.opportunity_id,
                "source_url": str(request.source_url),
                "change_detected": change_detected,
            },
            idempotency_key=request.idempotency_key,
        )
        return RulesSnapshotCaptureResult(
            snapshot_record_id=snapshot_record_id,
            capture_time=capture_time,
            normalized_hash=normalized_hash,
            raw_hash=raw_hash,
            previous_snapshot_record_id=previous_snapshot_record_id,
            change_detected=change_detected,
            diff_text=diff_text,
            freshness=freshness,
            evidence_archive_ids=evidence_archive_ids,
            ledger_record=ledger_record,
        )

    def _find_previous_snapshot(
        self,
        opportunity_id: str,
        source_url: str,
    ) -> LedgerEventEntry | None:
        candidates = self.ledger_service.get_related_events(related_type=RecordType.RULE_SNAPSHOT)
        for event in reversed(candidates):
            payload = event.payload.get("payload")
            if not isinstance(payload, dict):
                continue
            if (
                payload.get("opportunity_id") == opportunity_id
                and payload.get("source_url") == source_url
            ):
                return event
        return None

    def _record_failure(self, related_record_id: str, reason: str, **details: object) -> None:
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=related_record_id,
            event_name="rules_snapshot_capture_failed",
            payload={"reason": reason, **details},
        )

    @staticmethod
    def _normalize(value: str) -> str:
        normalized_lines = [line.rstrip() for line in value.replace("\r\n", "\n").split("\n")]
        return "\n".join(normalized_lines).strip()

    def _freshness(self, previous_created_at: str) -> SnapshotFreshness:
        try:
            parsed_previous = datetime.fromisoformat(previous_created_at)
        except ValueError:
            return SnapshotFreshness.UNKNOWN
        threshold = utc_now() - timedelta(hours=self.config.stale_after_hours)
        return SnapshotFreshness.FRESH if parsed_previous >= threshold else SnapshotFreshness.STALE
