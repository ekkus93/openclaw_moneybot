"""Local-only operator profile storage."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, cast

from pydantic import JsonValue

from openclaw_moneybot.plugins.support import (
    PluginHealthResult,
    json_mapping,
    record_plugin_audit_event,
)
from openclaw_moneybot.shared import OperatorProfileStoreConfig
from openclaw_moneybot.shared.types import ProfileAttributeAvailability, RecordType
from openclaw_moneybot.skills.account_eligibility_checker import OperatorProfile
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.support import record_structured_result
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now

from .models import (
    OperatorProfileFieldResult,
    OperatorProfileStoreReadRequest,
    OperatorProfileStoreReadResult,
    OperatorProfileStoreWriteRequest,
    OperatorProfileStoreWriteResult,
)

SENSITIVE_FIELD_MARKERS = {
    "credential",
    "secret",
    "token",
    "password",
    "government",
    "kyc",
    "document",
}


class OperatorProfileStore:
    """Store explicitly configured operator capabilities without secrets."""

    def __init__(
        self,
        config: OperatorProfileStoreConfig,
        ledger_service: LedgerService,
    ) -> None:
        self.config = config
        self.ledger_service = ledger_service

    def health(self) -> PluginHealthResult:
        """Return local health metadata."""

        return PluginHealthResult(
            plugin_name="operator_profile_store",
            enabled=self.config.enabled,
            read_only=False,
        )

    def upsert(self, request: OperatorProfileStoreWriteRequest) -> OperatorProfileStoreWriteResult:
        """Persist validated operator-profile data with provenance."""

        sensitive = [
            field_name
            for field_name in request.fields
            if any(marker in field_name.lower() for marker in SENSITIVE_FIELD_MARKERS)
        ]
        if sensitive:
            sensitive_fields = ", ".join(sorted(sensitive))
            msg = f"Sensitive operator profile fields are not allowed: {sensitive_fields}"
            raise ValueError(msg)
        allowed_fields = set(OperatorProfile.model_fields)
        unsupported = sorted(set(request.fields) - allowed_fields)
        if unsupported:
            msg = f"Unsupported operator profile fields: {', '.join(unsupported)}"
            raise ValueError(msg)

        stored_state = self._load_state()
        merged_fields: dict[str, JsonValue] = {
            **cast(dict[str, JsonValue], stored_state["fields"]),
            **request.fields,
        }
        profile = OperatorProfile.model_validate(merged_fields)
        last_updated = utc_now()
        profile_version = int(stored_state["profile_version"]) + 1
        persisted_fields = cast(
            dict[str, JsonValue],
            profile.model_dump(mode="json", exclude_none=True),
        )
        persisted = {
            "profile_version": profile_version,
            "last_updated": last_updated.isoformat(),
            "fields": persisted_fields,
            "provenance": {
                **cast(dict[str, str], stored_state["provenance"]),
                **request.provenance,
            },
        }
        self._write_state(persisted)

        profile_record_id = make_id("operator_profile")
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=profile_record_id,
            record_type=RecordType.OPERATOR_PROFILE_SNAPSHOT,
            related_record_id=profile_record_id,
            payload=persisted,
        )
        audit_record_id = record_plugin_audit_event(
            self.ledger_service,
            related_record_id=profile_record_id,
            event_name="operator_profile_store_upsert",
            payload={
                "profile_version": profile_version,
                "updated_fields": sorted(request.fields),
                "provenance_fields": sorted(request.provenance),
            },
            idempotency_key=request.idempotency_key,
        )
        return OperatorProfileStoreWriteResult(
            profile_version=profile_version,
            last_updated=last_updated,
            stored_profile=profile,
            ledger_record=ledger_record,
            audit_record_id=audit_record_id,
            redacted_export=self._redacted_export(persisted_fields),
        )

    def read(self, request: OperatorProfileStoreReadRequest) -> OperatorProfileStoreReadResult:
        """Read a safe subset of operator-profile fields."""

        stored_state = self._load_state()
        stored_profile = OperatorProfile.model_validate(stored_state["fields"])
        last_updated = self._parse_last_updated(stored_state["last_updated"])
        provenance = cast(dict[str, str], stored_state["provenance"])
        field_results: dict[str, OperatorProfileFieldResult] = {}
        stored_fields = cast(dict[str, JsonValue], stored_state["fields"])
        for field_name in request.field_names:
            if field_name in stored_fields:
                field_results[field_name] = OperatorProfileFieldResult(
                    availability=ProfileAttributeAvailability.CONFIGURED,
                    value=stored_fields[field_name],
                    provenance=provenance.get(field_name),
                    updated_at=last_updated,
                )
            elif any(marker in field_name.lower() for marker in SENSITIVE_FIELD_MARKERS):
                field_results[field_name] = OperatorProfileFieldResult(
                    availability=ProfileAttributeAvailability.REDACTED,
                    provenance=None,
                    updated_at=last_updated,
                )
            else:
                field_results[field_name] = OperatorProfileFieldResult(
                    availability=ProfileAttributeAvailability.UNKNOWN,
                    provenance=None,
                    updated_at=last_updated,
                )
        return OperatorProfileStoreReadResult(
            profile_version=int(stored_state["profile_version"]),
            last_updated=last_updated,
            stored_profile=stored_profile,
            field_results=field_results,
            redacted_export=self._redacted_export(stored_fields),
        )

    def get_operator_profile(self) -> OperatorProfile:
        """Return the stored profile for eligibility checks."""

        stored_state = self._load_state()
        return OperatorProfile.model_validate(stored_state["fields"])

    def _load_state(self) -> dict[str, Any]:
        path = self.config.profile_path
        if not path.exists():
            return {
                "profile_version": 0,
                "last_updated": None,
                "fields": {},
                "provenance": {},
            }
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            msg = "Operator profile store payload is malformed."
            raise ValueError(msg)
        return loaded

    def _write_state(self, payload: dict[str, object]) -> None:
        path = self.config.profile_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(json_mapping(payload), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _parse_last_updated(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        return datetime.fromisoformat(value)

    def _redacted_export(self, stored_fields: dict[str, JsonValue]) -> dict[str, JsonValue]:
        limited_items = list(sorted(stored_fields.items()))[: self.config.max_export_fields]
        redacted: dict[str, JsonValue] = {}
        for field_name, value in limited_items:
            if isinstance(value, list):
                redacted[field_name] = "[configured_list]"
            elif isinstance(value, bool | int):
                redacted[field_name] = "[configured]"
            else:
                redacted[field_name] = "[configured_value]"
        return redacted
