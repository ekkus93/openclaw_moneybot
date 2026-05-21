"""Capture bounded public counterparty snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast
from urllib.parse import urlparse

from openclaw_moneybot.plugins.counterparty_snapshot_plugin.models import (
    CounterpartySnapshotRequest,
    CounterpartySnapshotResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, CounterpartySnapshotConfig
from openclaw_moneybot.shared.types import (
    CounterpartyEvidenceTier,
    RecordType,
    SnapshotFreshness,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id

SUPPORTED_SOURCE_CATEGORIES = {
    "public_profile",
    "about_page",
    "payment_proof",
    "rules_page",
}
PRIVATE_PATH_MARKERS = {"login", "signin", "account", "dashboard", "private", "checkout"}


class CounterpartySnapshotPlugin:
    """Archive and compare public counterparty evidence only."""

    def __init__(
        self,
        config: CounterpartySnapshotConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
    ) -> None:
        self.config = config
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
        self.ledger_service = ledger_service

    def health(self) -> PluginHealthResult:
        return PluginHealthResult(
            plugin_name="counterparty_snapshot_plugin",
            enabled=self.config.enabled,
            read_only=False,
        )

    def capture(self, request: CounterpartySnapshotRequest) -> CounterpartySnapshotResult:
        """Capture one allowlisted public snapshot."""

        parsed_url = urlparse(request.source_url)
        host = (parsed_url.hostname or "").lower()
        if request.source_category not in SUPPORTED_SOURCE_CATEGORIES:
            msg = f"Unsupported source category: {request.source_category}"
            raise ValueError(msg)
        if host not in self.config.allowed_hosts:
            msg = f"Counterparty snapshot host is not allowlisted: {host}"
            raise ValueError(msg)
        if request.content_type.lower() not in self.config.allowed_content_types:
            msg = "Counterparty snapshot content type is not allowlisted."
            raise ValueError(msg)
        if len(request.content_text.encode("utf-8")) > self.config.max_content_bytes:
            msg = "Counterparty snapshot content exceeds the configured size limit."
            raise ValueError(msg)
        if any(marker in parsed_url.path.lower().split("/") for marker in PRIVATE_PATH_MARKERS):
            msg = "Counterparty snapshot URL must stay within public pages."
            raise ValueError(msg)

        fields = _parse_public_fields(request.content_text)
        if fields.get("robots_allowed") is False:
            msg = "Counterparty snapshot source is marked as disallowed for capture."
            raise ValueError(msg)
        indicators = _extract_indicators(fields, request.counterparty_name, host)
        missing_fields = [
            field_name
            for field_name in request.expected_fields
            if indicators.get(field_name) in {None, "", False}
        ]
        evidence_tier = _evidence_tier(
            expected_count=len(request.expected_fields),
            missing_count=len(missing_fields),
        )
        freshness = _freshness_for(
            captured_at=request.captured_at,
            current_time=request.current_time,
            freshness_days=self.config.freshness_days,
        )
        previous = self._find_previous_snapshot(
            counterparty_name=request.counterparty_name,
            source_category=request.source_category,
        )
        changed_fields = _changed_fields(previous, indicators)
        snapshot_id = make_id("counterparty_snapshot")
        raw_evidence = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.COUNTERPARTY_SNAPSHOT,
                related_id=snapshot_id,
                evidence_type="counterparty_snapshot_raw",
                content_text=request.content_text,
                notes="Public counterparty snapshot raw content",
            )
        )
        structured_snapshot = {
            "snapshot_id": snapshot_id,
            "counterparty_name": request.counterparty_name,
            "source_url": request.source_url,
            "source_category": request.source_category,
            "captured_at": request.captured_at.isoformat(),
            "freshness": freshness.value,
            "evidence_tier": evidence_tier.value,
            "indicators": indicators,
            "missing_fields": missing_fields,
            "changed_fields": changed_fields,
            "previous_snapshot_id": (
                None
                if previous is None
                else previous.get("snapshot_id") or previous.get("record_id")
            ),
        }
        snapshot_evidence = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.COUNTERPARTY_SNAPSHOT,
            related_id=snapshot_id,
            evidence_type="counterparty_snapshot_structured",
            payload=structured_snapshot,
            notes="Structured public counterparty snapshot",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=snapshot_id,
            record_type=RecordType.COUNTERPARTY_SNAPSHOT,
            related_record_id=request.opportunity_id,
            payload={
                **structured_snapshot,
                "evidence_archive_ids": [raw_evidence.evidence_id, snapshot_evidence],
            },
        )
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=snapshot_id,
            event_name="counterparty_snapshot_captured",
            payload={
                "source_category": request.source_category,
                "host": host,
                "changed_fields": changed_fields,
            },
        )
        return CounterpartySnapshotResult(
            snapshot_id=snapshot_id,
            source_category=request.source_category,
            source_url=request.source_url,
            captured_at=request.captured_at,
            freshness=freshness,
            evidence_tier=evidence_tier,
            indicators=indicators,
            missing_fields=missing_fields,
            changed_fields=changed_fields,
            previous_snapshot_id=(
                None
                if previous is None
                else str(previous.get("snapshot_id") or previous.get("record_id"))
            ),
            evidence_archive_ids=[raw_evidence.evidence_id, snapshot_evidence],
            ledger_record=ledger_record,
        )

    def _find_previous_snapshot(
        self,
        *,
        counterparty_name: str,
        source_category: str,
    ) -> dict[str, object] | None:
        matches: list[tuple[str, dict[str, object]]] = []
        for event in self.ledger_service.get_related_events(
            related_type=RecordType.COUNTERPARTY_SNAPSHOT
        ):
            payload = event.payload.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("counterparty_name") != counterparty_name:
                continue
            if payload.get("source_category") != source_category:
                continue
            captured_at = payload.get("captured_at")
            if not isinstance(captured_at, str):
                continue
            matches.append((captured_at, cast(dict[str, object], payload)))
        if not matches:
            return None
        matches.sort(key=lambda item: item[0])
        return matches[-1][1]


def _parse_public_fields(content_text: str) -> dict[str, str | bool | int]:
    parsed: dict[str, str | bool | int] = {}
    for raw_line in content_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        separator = ":" if ":" in line else "=" if "=" in line else None
        if separator is None:
            continue
        key, value = line.split(separator, 1)
        normalized_key = "_".join(key.strip().lower().split())
        normalized_value = value.strip()
        bool_value = _parse_bool(normalized_value)
        if bool_value is not None:
            parsed[normalized_key] = bool_value
            continue
        if normalized_value.isdigit():
            parsed[normalized_key] = int(normalized_value)
            continue
        parsed[normalized_key] = normalized_value
    return parsed


def _extract_indicators(
    parsed_fields: dict[str, str | bool | int],
    counterparty_name: str,
    host: str,
) -> dict[str, object]:
    support_email = parsed_fields.get("support_email")
    return {
        "display_name": str(parsed_fields.get("display_name") or counterparty_name),
        "platform_domain": host,
        "support_email": (
            str(support_email) if isinstance(support_email, str) and "@" in support_email else None
        ),
        "payout_terms_present": _bool_field(parsed_fields.get("payout_terms_present")),
        "payment_proof_present": _bool_field(parsed_fields.get("payment_proof_present")),
        "dispute_policy_present": _bool_field(parsed_fields.get("dispute_policy_present")),
        "support_responsive": _bool_field(parsed_fields.get("support_responsive")),
        "domain_age_days": _int_field(parsed_fields.get("domain_age_days")),
        "public_since": _string_field(parsed_fields.get("public_since")),
    }


def _changed_fields(
    previous: dict[str, object] | None,
    indicators: dict[str, object],
) -> list[str]:
    if previous is None:
        return sorted(indicators)
    previous_indicators = previous.get("indicators")
    if not isinstance(previous_indicators, dict):
        return sorted(indicators)
    changed: list[str] = []
    for key, value in indicators.items():
        if previous_indicators.get(key) != value:
            changed.append(key)
    return sorted(changed)


def _evidence_tier(*, expected_count: int, missing_count: int) -> CounterpartyEvidenceTier:
    if missing_count >= expected_count:
        return CounterpartyEvidenceTier.INCOMPLETE
    if missing_count == 0:
        return CounterpartyEvidenceTier.STRONG
    if missing_count <= 2:
        return CounterpartyEvidenceTier.PARTIAL
    return CounterpartyEvidenceTier.WEAK


def _freshness_for(
    *,
    captured_at: datetime,
    current_time: datetime | None,
    freshness_days: int,
) -> SnapshotFreshness:
    if current_time is None:
        return SnapshotFreshness.UNKNOWN
    if current_time - captured_at <= timedelta(days=freshness_days):
        return SnapshotFreshness.FRESH
    return SnapshotFreshness.STALE


def _parse_bool(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered in {"yes", "true", "present", "allowed"}:
        return True
    if lowered in {"no", "false", "missing", "blocked"}:
        return False
    return None


def _bool_field(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _int_field(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _string_field(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
