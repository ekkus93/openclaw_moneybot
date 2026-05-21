"""Shared helpers for structured skill outputs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from pydantic import JsonValue

from openclaw_moneybot.shared import LedgerRecord
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.utils.time import utc_now


def archive_json_snapshot(
    archiver: ReceiptAndEvidenceArchiver,
    *,
    related_type: RecordType,
    related_id: str,
    evidence_type: str,
    payload: Mapping[str, object],
    notes: str,
) -> str:
    """Archive a deterministic JSON snapshot and return the evidence id."""
    json_ready = cast(dict[str, JsonValue], json.loads(json.dumps(payload, sort_keys=True)))
    archived = archiver.archive(
        EvidenceArchiveRequest(
            related_type=related_type,
            related_id=related_id,
            evidence_type=evidence_type,
            content_text=json.dumps(json_ready, indent=2, sort_keys=True),
            notes=notes,
        )
    )
    return archived.evidence_id


def record_structured_result(
    ledger_service: LedgerService,
    *,
    record_id: str,
    record_type: RecordType,
    related_record_id: str,
    payload: Mapping[str, object],
) -> LedgerRecord:
    """Write a generic structured ledger record for new skill outputs."""
    json_ready = cast(dict[str, JsonValue], json.loads(json.dumps(payload, sort_keys=True)))
    record = LedgerRecord(
        created_at=utc_now(),
        record_id=record_id,
        record_type=record_type,
        related_record_id=related_record_id,
        payload=json_ready,
    )
    ledger_service.record_ledger_record(
        record,
        idempotency_key=f"{record_type.value}:{record_id}",
    )
    return record
