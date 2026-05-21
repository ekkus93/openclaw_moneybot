"""Unit tests for the metrics export plugin."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from openclaw_moneybot.plugins.metrics_export_plugin import (
    MetricsExportPlugin,
    MetricsExportRequest,
)
from openclaw_moneybot.plugins.metrics_export_plugin.service import (
    _build_summary,
    _csv_ready_row,
    _opportunity_id_for_event,
    _record_payload,
)
from openclaw_moneybot.shared import ArchiveConfig, LedgerRecord, MetricsExportConfig, Opportunity
from openclaw_moneybot.shared.types import RecordType, RiskLevel
from openclaw_moneybot.skills.ledger_skill.models import LedgerEventEntry
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.support import record_structured_result


def make_plugin(
    tmp_path: Path,
    *,
    max_rows: int = 1_000,
) -> tuple[MetricsExportPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = MetricsExportPlugin(
        MetricsExportConfig(
            enabled=True,
            export_root=tmp_path / "exports",
            max_rows=max_rows,
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )
    return plugin, ledger_service


def seed_opportunity(ledger_service: LedgerService, *, opportunity_id: str = "opp_001") -> None:
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id=opportunity_id,
            name="Example opportunity",
            category="bounty",
            status="open",
            source_url="https://example.com/opportunity",
            required_spend_usd=0,
            estimated_revenue_usd=25,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key=f"opportunity:{opportunity_id}",
    )


def seed_experiment_review(
    ledger_service: LedgerService,
    *,
    review_id: str,
    opportunity_id: str = "opp_001",
    decision: str = "continue",
    created_at: str = "2026-01-02T00:00:00+00:00",
    manual_notes: str = "sensitive note",
) -> None:
    record_structured_result(
        ledger_service,
        record_id=review_id,
        record_type=RecordType.EXPERIMENT_REVIEW,
        related_record_id=opportunity_id,
        payload={
            "experiment_review_id": review_id,
            "created_at": created_at,
            "decision": decision,
            "status": "completed",
            "net_usd": 10.0,
            "roi_percent": 100.0,
            "time_spent_hours": 1.5,
            "evidence_quality": "strong",
            "manual_notes": manual_notes,
        },
    )


def seed_experiment_review_event(
    ledger_service: LedgerService,
    *,
    review_id: str,
    opportunity_id: str = "opp_001",
    decision: str = "continue",
    created_at: str = "2026-01-02T00:00:00+00:00",
) -> None:
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=datetime.fromisoformat(created_at),
            record_id=review_id,
            record_type=RecordType.EXPERIMENT_REVIEW,
            related_record_id=opportunity_id,
            payload={
                "experiment_review_id": review_id,
                "decision": decision,
                "status": "completed",
                "net_usd": 10.0,
                "roi_percent": 100.0,
                "time_spent_hours": 1.5,
                "evidence_quality": "strong",
            },
        ),
        idempotency_key=f"review-event:{review_id}",
    )


def seed_strategy_summary(
    ledger_service: LedgerService,
    *,
    summary_id: str = "summary_001",
    opportunity_id: str = "opp_001",
) -> None:
    record_structured_result(
        ledger_service,
        record_id=summary_id,
        record_type=RecordType.STRATEGY_SUMMARY,
        related_record_id=opportunity_id,
        payload={
            "summary_id": summary_id,
            "scope": "global",
            "lesson_categories": ["budgeting", "queue"],
            "what_worked": ["Positive net outcome."],
            "what_failed": [],
        },
    )


def seed_payout_reconciliation(
    ledger_service: LedgerService,
    *,
    reconciliation_id: str,
    opportunity_id: str = "opp_001",
    status: str = "matched",
    created_at: str = "2026-01-03T00:00:00+00:00",
) -> None:
    record_structured_result(
        ledger_service,
        record_id=reconciliation_id,
        record_type=RecordType.PAYOUT_RECONCILIATION,
        related_record_id=opportunity_id,
        payload={
            "reconciliation_id": reconciliation_id,
            "created_at": created_at,
            "status": status,
            "expected_amount": 10.0,
            "observed_amount": 10.0,
            "variance": 0.0,
            "followup_recommended": status != "matched",
        },
    )


def test_approved_export_succeeds_with_stable_output_ordering(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    seed_opportunity(ledger_service)
    seed_experiment_review(ledger_service, review_id="review_002", decision="stop")
    seed_experiment_review(ledger_service, review_id="review_001", decision="continue")

    first = plugin.export(
        MetricsExportRequest(export_type="experiment_reviews", output_format="json")
    )
    second = plugin.export(
        MetricsExportRequest(export_type="experiment_reviews", output_format="json")
    )

    first_rows = json.loads(first.output_path.read_text(encoding="utf-8"))
    second_rows = json.loads(second.output_path.read_text(encoding="utf-8"))

    assert [row["experiment_review_id"] for row in first_rows] == ["review_001", "review_002"]
    assert first_rows == second_rows


def test_unsupported_filter_is_rejected(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    seed_opportunity(ledger_service)
    seed_strategy_summary(ledger_service)

    with pytest.raises(ValueError, match="not supported"):
        plugin.export(
            MetricsExportRequest(
                export_type="strategy_summaries",
                outcome_category="continue",
            )
        )


def test_sensitive_fields_are_excluded(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    seed_opportunity(ledger_service)
    seed_experiment_review(ledger_service, review_id="review_001", manual_notes="secret")

    result = plugin.export(MetricsExportRequest(export_type="experiment_reviews"))
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert "manual_notes" not in rows[0]


def test_oversized_export_request_is_bounded_safely(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path, max_rows=1)
    seed_opportunity(ledger_service)
    seed_experiment_review(ledger_service, review_id="review_001")
    seed_experiment_review(ledger_service, review_id="review_002")

    result = plugin.export(MetricsExportRequest(export_type="experiment_reviews", limit=10))

    assert result.status.value == "bounded"
    assert result.row_count == 1


def test_export_metadata_and_audit_linkage_are_preserved(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    seed_opportunity(ledger_service)
    seed_experiment_review(ledger_service, review_id="review_001")

    result = plugin.export(
        MetricsExportRequest(export_type="experiment_reviews", output_format="csv")
    )
    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)

    assert result.evidence_archive_ids
    assert any(
        isinstance(event.payload.get("payload"), dict)
        and (
            cast(dict[str, object], event.payload["payload"]).get("event_name")
            == "metrics_export_completed"
        )
        and event.payload.get("related_record_id") == result.export_job_id
        for event in audit_events
    )


def test_unsupported_export_type_is_rejected(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="Unsupported metrics export type"):
        plugin.export(MetricsExportRequest(export_type="unknown"))


def test_unsupported_export_format_is_rejected(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="Unsupported metrics export format"):
        plugin.export(MetricsExportRequest(export_type="experiment_reviews", output_format="xml"))


@pytest.mark.parametrize("export_type", ["experiment_reviews", "payout_reconciliations"])
def test_unsupported_outcome_value_is_rejected(
    tmp_path: Path,
    export_type: str,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="Unsupported outcome filter"):
        plugin.export(
            MetricsExportRequest(
                export_type=export_type,
                outcome_category="not-real",
            )
        )


def test_experiment_review_rows_include_missing_typed_opportunity(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    seed_experiment_review(ledger_service, review_id="review_001", opportunity_id="opp_missing")

    result = plugin.export(MetricsExportRequest(export_type="experiment_reviews"))
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert rows[0]["opportunity_category"] is None
    assert rows[0]["opportunity_id"] == "opp_missing"


def test_experiment_review_filters_apply_to_day_category_and_outcome(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    seed_opportunity(ledger_service, opportunity_id="opp_001")
    seed_opportunity(ledger_service, opportunity_id="opp_002")
    seed_experiment_review_event(
        ledger_service,
        review_id="review_early",
        created_at="2026-01-01T00:00:00+00:00",
    )
    seed_experiment_review_event(
        ledger_service,
        review_id="review_keep",
        decision="stop",
        created_at="2026-01-03T00:00:00+00:00",
    )
    seed_experiment_review_event(
        ledger_service,
        review_id="review_other",
        opportunity_id="opp_002",
        decision="stop",
        created_at="2026-01-03T00:00:00+00:00",
    )

    result = plugin.export(
        MetricsExportRequest(
            export_type="experiment_reviews",
            start_day="2026-01-02",
            end_day="2026-01-03",
            opportunity_category="bounty",
            outcome_category="stop",
        )
    )
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert [row["experiment_review_id"] for row in rows] == ["review_keep", "review_other"]


def test_payout_export_rows_and_summary_counts_are_built(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    seed_opportunity(ledger_service)
    seed_payout_reconciliation(ledger_service, reconciliation_id="recon_1", status="matched")
    seed_payout_reconciliation(ledger_service, reconciliation_id="recon_2", status="late")

    result = plugin.export(
        MetricsExportRequest(
            export_type="payout_reconciliations",
            outcome_category="late",
        )
    )
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert [row["status"] for row in rows] == ["late"]
    assert result.summary["outcome_counts"] == {"late": 1}


def test_strategy_export_handles_non_list_lesson_categories(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    seed_opportunity(ledger_service)
    record_structured_result(
        ledger_service,
        record_id="summary_bad",
        record_type=RecordType.STRATEGY_SUMMARY,
        related_record_id="opp_001",
        payload={
            "scope": "global",
            "lesson_categories": "bad",
            "what_worked": ["x"],
            "what_failed": [],
        },
    )

    result = plugin.export(MetricsExportRequest(export_type="strategy_summaries"))
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert rows[0]["lesson_categories"] == ""


def test_strategy_export_counts_work_lists_and_filters_category(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    seed_opportunity(ledger_service, opportunity_id="opp_001")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_002",
            name="Example opportunity",
            category="survey",
            status="open",
            source_url="https://example.com/survey",
            required_spend_usd=0,
            estimated_revenue_usd=25,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key="opportunity:opp_002",
    )
    seed_strategy_summary(ledger_service, summary_id="summary_1", opportunity_id="opp_001")
    seed_strategy_summary(ledger_service, summary_id="summary_2", opportunity_id="opp_002")

    result = plugin.export(
        MetricsExportRequest(
            export_type="strategy_summaries",
            opportunity_category="bounty",
        )
    )
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert len(rows) == 1
    assert rows[0]["what_worked_count"] == 1
    assert rows[0]["what_failed_count"] == 0


def test_resolve_output_path_rejects_export_root_escape(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)
    safe_root = tmp_path / "safe-root"
    outside_root = tmp_path / "outside-root"
    safe_root.mkdir()
    outside_root.mkdir()
    (safe_root / "experiment_reviews").symlink_to(outside_root, target_is_directory=True)
    plugin.config.export_root = safe_root

    with pytest.raises(ValueError, match="escaped"):
        plugin._resolve_output_path(
            "export_001",
            MetricsExportRequest(export_type="experiment_reviews"),
        )


def test_write_output_handles_empty_json_and_csv_rows(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)
    json_path = tmp_path / "empty.json"
    csv_path = tmp_path / "empty.csv"

    plugin._write_output(json_path, [], "json")
    plugin._write_output(csv_path, [], "csv")

    assert json.loads(json_path.read_text(encoding="utf-8")) == []
    assert csv_path.read_text(encoding="utf-8") in {"\n", "\r\n"}


def test_helper_functions_cover_fallback_branches() -> None:
    event = LedgerEventEntry(
        ledger_event_id="evt_001",
        created_at="2026-01-01T00:00:00+00:00",
        event_type="record_strategy_summary",
        related_type=RecordType.STRATEGY_SUMMARY,
        related_id="summary_001",
        payload={"scope": "global"},
    )

    assert _record_payload(event) == {"scope": "global"}
    assert _opportunity_id_for_event(event) == "summary_001"
    assert _csv_ready_row({"a": None, "b": 1}) == {"a": "", "b": "1"}
    assert _build_summary(
        export_type="strategy_summaries",
        rows=[{"scope": "global"}],
        bounded=False,
        effective_limit=10,
    )["outcome_counts"] == {}


def test_bounded_export_with_no_rows_still_records_outputs(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, max_rows=1)

    result = plugin.export(MetricsExportRequest(export_type="strategy_summaries"))

    assert result.row_count == 0
    assert result.output_path.exists() is True
    assert result.evidence_archive_ids
