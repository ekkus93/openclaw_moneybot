"""Produce bounded local metrics exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from openclaw_moneybot.plugins.metrics_export_plugin.models import (
    MetricsExportRequest,
    MetricsExportResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, MetricsExportConfig
from openclaw_moneybot.shared.types import ExportJobStatus, RecordType
from openclaw_moneybot.skills.ledger_skill.models import LedgerEventEntry
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id

APPROVED_EXPORT_TYPES = {
    "experiment_reviews",
    "payout_reconciliations",
    "strategy_summaries",
}
APPROVED_OUTPUT_FORMATS = {"json", "csv"}
EXPERIMENT_REVIEW_OUTCOMES = {
    "continue",
    "stop",
    "retry_with_changes",
    "human_review",
    "block_category",
}
PAYOUT_OUTCOMES = {
    "matched",
    "partial",
    "missing",
    "late",
    "underpaid",
    "overpaid_needs_review",
    "ambiguous_needs_review",
}


class MetricsExportPlugin:
    """Export approved ledger-backed metrics without exposing raw queries."""

    def __init__(
        self,
        config: MetricsExportConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
    ) -> None:
        self.config = config
        archive_allowed_roots = [*archive_config.allowed_source_roots, config.export_root]
        self.archiver = ReceiptAndEvidenceArchiver(
            archive_config.model_copy(update={"allowed_source_roots": archive_allowed_roots}),
            ledger_service,
        )
        self.ledger_service = ledger_service

    def health(self) -> PluginHealthResult:
        return PluginHealthResult(
            plugin_name="metrics_export_plugin",
            enabled=self.config.enabled,
            read_only=False,
        )

    def export(self, request: MetricsExportRequest) -> MetricsExportResult:
        """Export one approved report shape with deterministic ordering."""

        if request.export_type not in APPROVED_EXPORT_TYPES:
            msg = f"Unsupported metrics export type: {request.export_type}"
            raise ValueError(msg)
        if request.output_format not in APPROVED_OUTPUT_FORMATS:
            msg = f"Unsupported metrics export format: {request.output_format}"
            raise ValueError(msg)
        self._validate_filter(request)

        rows = self._build_rows(request)
        rows.sort(
            key=lambda item: (
                str(item.get("opportunity_id", "")),
                str(item.get("experiment_review_id", "")),
                str(item.get("reconciliation_id", "")),
                str(item.get("summary_id", "")),
                str(item.get("created_at", "")),
            )
        )
        effective_limit = min(request.limit, self.config.max_rows)
        bounded = len(rows) > effective_limit or request.limit > self.config.max_rows
        selected_rows = rows[:effective_limit]
        export_job_id = make_id("metrics_export")
        output_path = self._resolve_output_path(export_job_id, request)
        self._write_output(output_path, selected_rows, request.output_format)
        file_evidence = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.METRICS_EXPORT,
                related_id=export_job_id,
                evidence_type=f"metrics_export_{request.output_format}",
                content_bytes_path=output_path,
                notes="Bounded metrics export output",
            )
        )
        summary = _build_summary(
            export_type=request.export_type,
            rows=selected_rows,
            bounded=bounded,
            effective_limit=effective_limit,
        )
        summary_evidence = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.METRICS_EXPORT,
            related_id=export_job_id,
            evidence_type="metrics_export_summary",
            payload=summary,
            notes="Metrics export summary",
        )
        status = ExportJobStatus.BOUNDED if bounded else ExportJobStatus.COMPLETED
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=export_job_id,
            record_type=RecordType.METRICS_EXPORT,
            related_record_id=export_job_id,
            payload={
                "export_type": request.export_type,
                "output_format": request.output_format,
                "output_path": str(output_path),
                "row_count": len(selected_rows),
                "status": status.value,
                "filters": request.model_dump(mode="json"),
                "summary": summary,
                "evidence_archive_ids": [file_evidence.evidence_id, summary_evidence],
            },
        )
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=export_job_id,
            event_name="metrics_export_completed",
            payload={
                "export_type": request.export_type,
                "bounded": bounded,
                "row_count": len(selected_rows),
            },
        )
        return MetricsExportResult(
            export_job_id=export_job_id,
            status=status,
            output_path=output_path,
            row_count=len(selected_rows),
            summary=summary,
            evidence_archive_ids=[file_evidence.evidence_id, summary_evidence],
            ledger_record=ledger_record,
        )

    def _validate_filter(self, request: MetricsExportRequest) -> None:
        if request.outcome_category is None:
            return
        allowed_outcomes: set[str]
        if request.export_type == "experiment_reviews":
            allowed_outcomes = EXPERIMENT_REVIEW_OUTCOMES
        elif request.export_type == "payout_reconciliations":
            allowed_outcomes = PAYOUT_OUTCOMES
        else:
            msg = "Outcome-category filtering is not supported for this export type."
            raise ValueError(msg)
        if request.outcome_category not in allowed_outcomes:
            msg = f"Unsupported outcome filter: {request.outcome_category}"
            raise ValueError(msg)

    def _build_rows(self, request: MetricsExportRequest) -> list[dict[str, object]]:
        if request.export_type == "experiment_reviews":
            return self._build_experiment_review_rows(request)
        if request.export_type == "payout_reconciliations":
            return self._build_payout_rows(request)
        return self._build_strategy_rows(request)

    def _build_experiment_review_rows(
        self,
        request: MetricsExportRequest,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for event in self.ledger_service.get_related_events(
            related_type=RecordType.EXPERIMENT_REVIEW
        ):
            payload = _record_payload(event)
            opportunity_id = _opportunity_id_for_event(event)
            opportunity = self.ledger_service.get_opportunity(opportunity_id)
            decision = _string_field(payload.get("decision"))
            if not self._event_matches_filters(
                event,
                request=request,
                opportunity_category=None if opportunity is None else opportunity.category,
                outcome=decision,
            ):
                continue
            rows.append(
                {
                    "created_at": event.created_at,
                    "experiment_review_id": _string_field(payload.get("experiment_review_id"))
                    or _string_field(event.payload.get("record_id"))
                    or opportunity_id,
                    "opportunity_id": opportunity_id,
                    "opportunity_category": None if opportunity is None else opportunity.category,
                    "decision": decision,
                    "status": _string_field(payload.get("status")),
                    "net_usd": _float_field(payload.get("net_usd")),
                    "roi_percent": _float_field(payload.get("roi_percent")),
                    "time_spent_hours": _float_field(payload.get("time_spent_hours")),
                    "evidence_quality": _string_field(payload.get("evidence_quality")),
                }
            )
        return rows

    def _build_payout_rows(self, request: MetricsExportRequest) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for event in self.ledger_service.get_related_events(
            related_type=RecordType.PAYOUT_RECONCILIATION
        ):
            payload = _record_payload(event)
            opportunity_id = _opportunity_id_for_event(event)
            opportunity = self.ledger_service.get_opportunity(opportunity_id)
            status = _string_field(payload.get("status"))
            if not self._event_matches_filters(
                event,
                request=request,
                opportunity_category=None if opportunity is None else opportunity.category,
                outcome=status,
            ):
                continue
            rows.append(
                {
                    "created_at": event.created_at,
                    "reconciliation_id": _string_field(event.payload.get("record_id"))
                    or opportunity_id,
                    "opportunity_id": opportunity_id,
                    "opportunity_category": None if opportunity is None else opportunity.category,
                    "status": status,
                    "expected_amount": _float_field(payload.get("expected_amount")),
                    "observed_amount": _float_field(payload.get("observed_amount")),
                    "variance": _float_field(payload.get("variance")),
                    "followup_recommended": _bool_field(payload.get("followup_recommended")),
                }
            )
        return rows

    def _build_strategy_rows(self, request: MetricsExportRequest) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for event in self.ledger_service.get_related_events(
            related_type=RecordType.STRATEGY_SUMMARY
        ):
            payload = _record_payload(event)
            opportunity_id = _opportunity_id_for_event(event)
            opportunity = self.ledger_service.get_opportunity(opportunity_id)
            if not self._event_matches_filters(
                event,
                request=request,
                opportunity_category=None if opportunity is None else opportunity.category,
                outcome=None,
            ):
                continue
            lesson_categories = payload.get("lesson_categories")
            rows.append(
                {
                    "created_at": event.created_at,
                    "summary_id": _string_field(event.payload.get("record_id")) or opportunity_id,
                    "opportunity_id": opportunity_id,
                    "opportunity_category": None if opportunity is None else opportunity.category,
                    "scope": _string_field(payload.get("scope")),
                    "lesson_categories": (
                        ",".join(str(item) for item in lesson_categories)
                        if isinstance(lesson_categories, list)
                        else ""
                    ),
                    "what_worked_count": _list_count(payload.get("what_worked")),
                    "what_failed_count": _list_count(payload.get("what_failed")),
                }
            )
        return rows

    def _event_matches_filters(
        self,
        event: LedgerEventEntry,
        *,
        request: MetricsExportRequest,
        opportunity_category: str | None,
        outcome: str | None,
    ) -> bool:
        event_day = event.created_at[:10]
        if request.start_day is not None and event_day < request.start_day:
            return False
        if request.end_day is not None and event_day > request.end_day:
            return False
        if (
            request.opportunity_category is not None
            and opportunity_category != request.opportunity_category
        ):
            return False
        if request.outcome_category is not None and outcome != request.outcome_category:
            return False
        return True

    def _resolve_output_path(
        self,
        export_job_id: str,
        request: MetricsExportRequest,
    ) -> Path:
        output_dir = (self.config.export_root / request.export_type).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{export_job_id}.{request.output_format}"
        if not str(output_path.resolve()).startswith(str(self.config.export_root.resolve())):
            msg = "Metrics export path escaped the configured export root."
            raise ValueError(msg)
        return output_path

    def _write_output(
        self,
        output_path: Path,
        rows: list[dict[str, object]],
        output_format: str,
    ) -> None:
        if output_format == "json":
            output_path.write_text(
                json.dumps(rows, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return
        fieldnames = sorted({key for row in rows for key in row})
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(_csv_ready_row(row))


def _build_summary(
    *,
    export_type: str,
    rows: list[dict[str, object]],
    bounded: bool,
    effective_limit: int,
) -> dict[str, object]:
    outcome_counts: dict[str, int] = {}
    for row in rows:
        outcome = _string_field(row.get("decision")) or _string_field(row.get("status"))
        if outcome is None:
            continue
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
    return {
        "export_type": export_type,
        "row_count": len(rows),
        "bounded": bounded,
        "effective_limit": effective_limit,
        "outcome_counts": outcome_counts,
    }


def _record_payload(event: LedgerEventEntry) -> dict[str, object]:
    payload = event.payload.get("payload")
    if isinstance(payload, dict):
        return payload
    return event.payload


def _opportunity_id_for_event(event: LedgerEventEntry) -> str:
    related_record_id = event.payload.get("related_record_id")
    if isinstance(related_record_id, str):
        return related_record_id
    return event.related_id


def _csv_ready_row(row: dict[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in row.items():
        if value is None:
            result[key] = ""
        else:
            result[key] = str(value)
    return result


def _string_field(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _float_field(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _bool_field(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _list_count(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    return 0
