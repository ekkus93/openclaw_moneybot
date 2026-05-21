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
from openclaw_moneybot.shared import ArchiveConfig, MetricsExportConfig, Opportunity
from openclaw_moneybot.shared.types import RecordType, RiskLevel
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
