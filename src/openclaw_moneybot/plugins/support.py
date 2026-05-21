"""Shared helpers for plugin outputs and audit records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from pydantic import JsonValue

from openclaw_moneybot.shared import LedgerRecord
from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class PluginHealthResult(MoneyBotModel):
    """Shared health-check output for local plugins."""

    plugin_name: str
    status: str = "ok"
    enabled: bool
    read_only: bool = True


def json_mapping(payload: Mapping[str, object]) -> dict[str, JsonValue]:
    """Normalize arbitrary mappings into JSON-safe dictionaries."""

    return cast(dict[str, JsonValue], json.loads(json.dumps(payload, sort_keys=True)))


def record_plugin_audit_event(
    ledger_service: LedgerService,
    *,
    related_record_id: str,
    event_name: str,
    payload: Mapping[str, object],
    idempotency_key: str | None = None,
) -> str:
    """Write a typed audit event for a plugin action."""

    audit_record_id = make_id("audit")
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=utc_now(),
            record_id=audit_record_id,
            record_type=RecordType.AUDIT_EVENT,
            related_record_id=related_record_id,
            payload={
                "event_name": event_name,
                "audit_record_id": audit_record_id,
                **json_mapping(payload),
            },
        ),
        idempotency_key=idempotency_key,
    )
    return audit_record_id
