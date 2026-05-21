"""Deterministic deadline storage and summaries."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from openclaw_moneybot.plugins.deadline_scheduler_plugin.models import (
    DeadlineQueryRequest,
    DeadlineQueryResult,
    DeadlineScheduleRequest,
    DeadlineScheduleResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import DeadlineSchedulerConfig
from openclaw_moneybot.shared.types import DeadlineState, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.support import record_structured_result
from openclaw_moneybot.utils.ids import make_id


class DeadlineSchedulerPlugin:
    """Track deadlines, retry windows, and cooldowns without side effects."""

    def __init__(
        self,
        config: DeadlineSchedulerConfig,
        ledger_service: LedgerService,
    ) -> None:
        self.config = config
        self.ledger_service = ledger_service

    def health(self) -> PluginHealthResult:
        return PluginHealthResult(
            plugin_name="deadline_scheduler_plugin",
            enabled=self.config.enabled,
            read_only=False,
        )

    def schedule(self, request: DeadlineScheduleRequest) -> DeadlineScheduleResult:
        """Store or update one deadline item."""

        entries = self._load_entries()
        parsed_deadline, confidence, uncertainty_reason = self._parse_deadline(request)
        state = self._state_for(
            current_time=request.current_time,
            deadline_at=parsed_deadline,
            cooldown_until=request.cooldown_until,
        )
        if self._has_conflict(entries, request.reference_id, parsed_deadline):
            state = DeadlineState.CONFLICTING
            record_plugin_audit_event(
                self.ledger_service,
                related_record_id=request.reference_id,
                event_name="deadline_conflict_detected",
                payload={"reference_id": request.reference_id},
            )
        event_id = make_id("deadline_event")
        entry: dict[str, object] = {
            "deadline_event_id": event_id,
            "reference_id": request.reference_id,
            "deadline_at": None if parsed_deadline is None else parsed_deadline.isoformat(),
            "confidence": confidence,
            "uncertainty_reason": uncertainty_reason,
            "state": state.value,
            "source_evidence_ids": request.source_evidence_ids,
            "cooldown_until": (
                None if request.cooldown_until is None else request.cooldown_until.isoformat()
            ),
            "retry_after": None if request.retry_after is None else request.retry_after.isoformat(),
        }
        entries.append(entry)
        if len(entries) > self.config.max_items:
            entries = entries[-self.config.max_items :]
        self._write_entries(entries)
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=event_id,
            record_type=RecordType.DEADLINE_EVENT,
            related_record_id=request.reference_id,
            payload=entry,
        )
        return DeadlineScheduleResult(
            deadline_event_id=event_id,
            state=state,
            deadline_at=parsed_deadline,
            confidence=confidence,
            uncertainty_reason=uncertainty_reason,
            source_evidence_ids=request.source_evidence_ids,
            ledger_record=ledger_record,
        )

    def summarize(self, request: DeadlineQueryRequest) -> DeadlineQueryResult:
        """Return bounded deadline summaries."""

        entries = self._load_entries()
        upcoming_reference_ids: list[str] = []
        overdue_reference_ids: list[str] = []
        uncertain_reference_ids: list[str] = []
        conflicting_reference_ids: list[str] = []
        cooling_down_reference_ids: list[str] = []
        upcoming_limit = request.current_time + timedelta(hours=request.upcoming_within_hours)
        for entry in entries:
            reference_id = str(entry["reference_id"])
            state = DeadlineState(str(entry["state"]))
            if state is DeadlineState.CONFLICTING:
                conflicting_reference_ids.append(reference_id)
                continue
            if state is DeadlineState.UNCERTAIN:
                uncertain_reference_ids.append(reference_id)
                continue
            if state is DeadlineState.COOLING_DOWN:
                cooling_down_reference_ids.append(reference_id)
                continue
            deadline_raw = entry.get("deadline_at")
            if not isinstance(deadline_raw, str):
                continue
            deadline_at = datetime.fromisoformat(deadline_raw)
            if deadline_at < request.current_time:
                overdue_reference_ids.append(reference_id)
            elif deadline_at <= upcoming_limit:
                upcoming_reference_ids.append(reference_id)
        summary_id = make_id("deadline_event")
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=summary_id,
            record_type=RecordType.DEADLINE_EVENT,
            related_record_id=summary_id,
            payload={
                "upcoming_reference_ids": upcoming_reference_ids,
                "overdue_reference_ids": overdue_reference_ids,
                "uncertain_reference_ids": uncertain_reference_ids,
                "conflicting_reference_ids": conflicting_reference_ids,
                "cooling_down_reference_ids": cooling_down_reference_ids,
            },
        )
        return DeadlineQueryResult(
            summary_id=summary_id,
            upcoming_reference_ids=upcoming_reference_ids,
            overdue_reference_ids=overdue_reference_ids,
            uncertain_reference_ids=uncertain_reference_ids,
            conflicting_reference_ids=conflicting_reference_ids,
            cooling_down_reference_ids=cooling_down_reference_ids,
            ledger_record=ledger_record,
        )

    def _load_entries(self) -> list[dict[str, object]]:
        path = self.config.schedule_path
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            msg = "Deadline schedule payload is malformed."
            raise ValueError(msg)
        return payload

    def _write_entries(self, payload: list[dict[str, object]]) -> None:
        path = self.config.schedule_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _parse_deadline(
        request: DeadlineScheduleRequest,
    ) -> tuple[datetime | None, str, str | None]:
        if request.deadline_at is not None:
            return request.deadline_at.astimezone(UTC), "high", None
        assert request.deadline_text is not None
        candidate = request.deadline_text.strip()
        if not candidate:
            return None, "low", "missing_deadline_text"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            try:
                parsed_date = datetime.strptime(candidate, "%Y-%m-%d")
            except ValueError:
                return None, "low", "ambiguous_deadline_text"
            return parsed_date.replace(tzinfo=UTC), "medium", None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC), "high", None

    @staticmethod
    def _state_for(
        *,
        current_time: datetime,
        deadline_at: datetime | None,
        cooldown_until: datetime | None,
    ) -> DeadlineState:
        if cooldown_until is not None and cooldown_until > current_time:
            return DeadlineState.COOLING_DOWN
        if deadline_at is None:
            return DeadlineState.UNCERTAIN
        if deadline_at < current_time:
            return DeadlineState.OVERDUE
        return DeadlineState.UPCOMING

    @staticmethod
    def _has_conflict(
        entries: list[dict[str, object]],
        reference_id: str,
        deadline_at: datetime | None,
    ) -> bool:
        if deadline_at is None:
            return False
        deadline_text = deadline_at.isoformat()
        for entry in entries:
            if entry.get("reference_id") != reference_id:
                continue
            existing_deadline = entry.get("deadline_at")
            if isinstance(existing_deadline, str) and existing_deadline != deadline_text:
                return True
        return False
