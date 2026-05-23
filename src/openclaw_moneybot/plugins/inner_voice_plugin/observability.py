"""Observability helpers for inner voice records and metrics."""

from __future__ import annotations

from collections.abc import Mapping

from openclaw_moneybot.plugins.support import record_plugin_audit_event
from openclaw_moneybot.shared import LedgerRecord
from openclaw_moneybot.shared.types import InnerVoiceStage, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id

from .models import InnerVoiceMetricsSnapshot


def persist_metrics_snapshot(
    snapshot: InnerVoiceMetricsSnapshot,
    *,
    ledger_service: LedgerService,
    archiver: ReceiptAndEvidenceArchiver,
    snapshot_id: str | None = None,
) -> LedgerRecord:
    """Persist one computed inner-voice metrics snapshot."""

    metrics_id = snapshot_id or make_id("inner_voice_metrics")
    summary_payload = snapshot.model_dump(mode="json")
    summary_evidence_id = archive_json_snapshot(
        archiver,
        related_type=RecordType.METRICS_EXPORT,
        related_id=metrics_id,
        evidence_type="metrics_export_summary",
        payload={
            "export_type": "inner_voice_metrics_snapshot",
            "summary": summary_payload,
        },
        notes="Inner voice metrics snapshot",
    )
    record = record_structured_result(
        ledger_service,
        record_id=metrics_id,
        record_type=RecordType.METRICS_EXPORT,
        related_record_id=metrics_id,
        payload={
            "export_type": "inner_voice_metrics_snapshot",
            "status": "completed",
            "summary": summary_payload,
            "evidence_archive_ids": [summary_evidence_id],
        },
    )
    record_plugin_audit_event(
        ledger_service,
        related_record_id=metrics_id,
        event_name="inner_voice_metrics_snapshot_persisted",
        payload={
            "metrics_id": metrics_id,
            "evidence_archive_id": summary_evidence_id,
        },
    )
    return record


def list_inner_voice_reviews(
    ledger_service: LedgerService,
    *,
    subject_id: str | None = None,
    stage: InnerVoiceStage | None = None,
    outcome: str | None = None,
) -> list[LedgerRecord]:
    """Return persisted inner-voice review records filtered by subject, stage, or outcome."""

    return _list_records(
        ledger_service,
        record_type=RecordType.INNER_VOICE_REVIEW,
        subject_id=subject_id,
        stage=stage,
        outcome=outcome,
    )


def list_inner_voice_debates(
    ledger_service: LedgerService,
    *,
    subject_id: str | None = None,
    stage: InnerVoiceStage | None = None,
    outcome: str | None = None,
) -> list[LedgerRecord]:
    """Return persisted debate records filtered by subject, stage, or outcome."""

    return _list_records(
        ledger_service,
        record_type=RecordType.INNER_VOICE_DEBATE,
        subject_id=subject_id,
        stage=stage,
        outcome=outcome,
    )


def list_arbiter_reviews(
    ledger_service: LedgerService,
    *,
    subject_id: str | None = None,
    stage: InnerVoiceStage | None = None,
    outcome: str | None = None,
) -> list[LedgerRecord]:
    """Return persisted Arbiter review records filtered by subject, stage, or outcome."""

    return _list_records(
        ledger_service,
        record_type=RecordType.ARBITER_REVIEW,
        subject_id=subject_id,
        stage=stage,
        outcome=outcome,
    )


def _list_records(
    ledger_service: LedgerService,
    *,
    record_type: RecordType,
    subject_id: str | None,
    stage: InnerVoiceStage | None,
    outcome: str | None,
) -> list[LedgerRecord]:
    stage_value = None if stage is None else stage.value
    events = ledger_service.get_related_events(
        related_type=record_type,
        event_type=f"record_{record_type.value}",
    )
    records: list[LedgerRecord] = []
    for event in events:
        record = LedgerRecord.model_validate(event.payload)
        payload = record.payload
        if subject_id is not None and payload.get("subject_id") != subject_id:
            continue
        if stage_value is not None and payload.get("stage") != stage_value:
            continue
        if outcome is not None and _record_outcome(payload) != outcome:
            continue
        records.append(record)
    return records


def _record_outcome(payload: Mapping[str, object]) -> str | None:
    for key in (
        "resolution_outcome",
        "final_resolution",
        "recommended_disposition",
        "resolved_disposition",
        "status",
    ):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None
