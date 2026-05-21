"""Integration coverage for the INT_TEST2 Phase C replay and export paths."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.plugins.artifact_renderer_plugin import (
    ArtifactRendererPlugin,
    ArtifactRenderRequest,
)
from openclaw_moneybot.plugins.metrics_export_plugin import (
    MetricsExportPlugin,
    MetricsExportRequest,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    ArtifactRendererConfig,
    LedgerRecord,
    MetricsExportConfig,
)
from openclaw_moneybot.shared.types import ReconciliationStatus, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.revenue_reconciler import (
    ReconciliationObservation,
    RevenueReconciler,
    RevenueReconciliationRequest,
)
from openclaw_moneybot.skills.submission_package_builder import (
    SubmissionPackageBuilder,
    SubmissionPackageBuildRequest,
)
from openclaw_moneybot.skills.terms_change_monitor import (
    TermsChangeMonitor,
    TermsChangeMonitorRequest,
)
from openclaw_moneybot.utils.time import utc_now

from .helpers import (
    make_archive_config,
    seed_budget_plan,
    seed_evidence_record,
    seed_opportunity,
    seed_policy_decision,
    seed_realistic_metrics_history,
    seed_rules_snapshot_pair,
    seed_tos_legal_check,
    write_submission_template,
)


def make_exporter(
    tmp_path: Path,
    archive_config: ArchiveConfig,
    ledger_service: LedgerService,
) -> MetricsExportPlugin:
    return MetricsExportPlugin(
        MetricsExportConfig(enabled=True, export_root=tmp_path / "exports"),
        archive_config,
        ledger_service,
    )


def make_renderer(
    tmp_path: Path,
    archive_config: ArchiveConfig,
    ledger_service: LedgerService,
) -> ArtifactRendererPlugin:
    template_root = tmp_path / "templates"
    write_submission_template(template_root, required_fields=["name", "email"])
    return ArtifactRendererPlugin(
        ArtifactRendererConfig(
            enabled=True,
            template_root=template_root,
            render_root=tmp_path / "rendered",
        ),
        archive_config,
        ledger_service,
    )


def test_metrics_export_experiment_reviews_match_real_history_in_json_and_csv(
    tmp_path: Path,
) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    history = seed_realistic_metrics_history(
        ledger_service,
        archive_config,
        opportunity_id="opp_001",
        category="bounty",
        expected_amount=20.0,
        revenue_usd=20.0,
        observed_amount=20.0,
    )
    exporter = make_exporter(tmp_path, archive_config, ledger_service)

    json_result = exporter.export(
        MetricsExportRequest(export_type="experiment_reviews", output_format="json")
    )
    csv_result = exporter.export(
        MetricsExportRequest(export_type="experiment_reviews", output_format="csv")
    )
    json_rows = json.loads(json_result.output_path.read_text(encoding="utf-8"))
    csv_rows = list(csv.DictReader(csv_result.output_path.read_text(encoding="utf-8").splitlines()))

    assert json_rows[0]["experiment_review_id"] == history["review"].experiment_review_id
    assert json_rows[0]["opportunity_id"] == "opp_001"
    assert json_result.output_path.is_relative_to(tmp_path / "exports") is True
    assert csv_rows[0]["experiment_review_id"] == history["review"].experiment_review_id
    assert json_result.evidence_archive_ids
    assert json_result.ledger_record.payload["row_count"] == 1


def test_metrics_export_payout_reconciliations_filter_real_history(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    seed_realistic_metrics_history(
        ledger_service,
        archive_config,
        opportunity_id="opp_001",
        category="bounty",
        expected_amount=20.0,
        revenue_usd=20.0,
        observed_amount=20.0,
    )
    late_history = seed_realistic_metrics_history(
        ledger_service,
        archive_config,
        opportunity_id="opp_002",
        category="survey",
        expected_amount=15.0,
        revenue_usd=0.0,
        observed_amount=None,
        current_date=datetime(2026, 1, 6, tzinfo=UTC),
    )
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=utc_now(),
            record_id="recon_missing_opp",
            record_type=RecordType.PAYOUT_RECONCILIATION,
            related_record_id="opp_missing",
            payload={
                "status": "late",
                "expected_amount": 50.0,
                "observed_amount": 0.0,
                "variance": -50.0,
                "followup_recommended": True,
            },
        )
    )
    exporter = make_exporter(tmp_path, archive_config, ledger_service)

    result = exporter.export(
        MetricsExportRequest(
            export_type="payout_reconciliations",
            output_format="json",
            opportunity_category="survey",
            outcome_category="late",
        )
    )
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert [row["opportunity_id"] for row in rows] == ["opp_002"]
    assert rows[0]["status"] == "late"
    assert result.summary["outcome_counts"] == {"late": 1}
    assert late_history["reconciliation"].status is ReconciliationStatus.LATE


def test_metrics_export_strategy_summaries_filter_real_history_safely(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    bounty_history = seed_realistic_metrics_history(
        ledger_service,
        archive_config,
        opportunity_id="opp_001",
        category="bounty",
        expected_amount=20.0,
        revenue_usd=20.0,
        observed_amount=20.0,
    )
    seed_realistic_metrics_history(
        ledger_service,
        archive_config,
        opportunity_id="opp_002",
        category="survey",
        expected_amount=15.0,
        revenue_usd=0.0,
        observed_amount=None,
        current_date=datetime(2026, 1, 6, tzinfo=UTC),
    )
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=utc_now(),
            record_id="summary_missing_opp",
            record_type=RecordType.STRATEGY_SUMMARY,
            related_record_id="opp_missing",
            payload={
                "scope": "opportunity",
                "lesson_categories": "not-a-list",
                "what_worked": "not-a-list",
                "what_failed": None,
            },
        )
    )
    exporter = make_exporter(tmp_path, archive_config, ledger_service)

    result = exporter.export(
        MetricsExportRequest(
            export_type="strategy_summaries",
            output_format="json",
            opportunity_category="bounty",
        )
    )
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert [row["opportunity_id"] for row in rows] == ["opp_001"]
    assert rows[0]["summary_id"] == bounty_history["summary"].summary_id
    assert rows[0]["what_worked_count"] >= 1
    assert rows[0]["what_failed_count"] >= 0


def test_replayed_submission_package_and_render_requests_remain_deterministic(
    tmp_path: Path,
) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    seed_opportunity(ledger_service)
    seed_policy_decision(ledger_service)
    seed_tos_legal_check(ledger_service)
    seed_budget_plan(ledger_service)
    evidence = seed_evidence_record(ledger_service)
    builder = SubmissionPackageBuilder(archive_config, ledger_service)
    renderer = make_renderer(tmp_path, archive_config, ledger_service)
    request = SubmissionPackageBuildRequest(
        opportunity_id="opp_001",
        opportunity_name="Integration opportunity",
        rules_text=(
            "Required fields: name, email\n"
            "Attachments: screenshot\n"
            "Submit at https://example.com/submit"
        ),
        source_url="https://example.com/submit",
        policy_decision_id="policy_001",
        tos_legal_check_id="tos_001",
        budget_plan_id="budget_001",
        evidence_archive_ids=[evidence.evidence_id],
    )

    package_one = builder.build(request)
    package_two = builder.build(request)
    render_one = renderer.render(
        ArtifactRenderRequest(
            related_record_id="opp_001",
            template_name="submission",
            field_values={"name": "Maintainer", "email": "maintainer@example.com"},
            evidence_archive_ids=[evidence.evidence_id],
        )
    )
    render_two = renderer.render(
        ArtifactRenderRequest(
            related_record_id="opp_001",
            template_name="submission",
            field_values={"name": "Maintainer", "email": "maintainer@example.com"},
            evidence_archive_ids=[evidence.evidence_id],
        )
    )

    assert package_one.status == package_two.status
    assert package_one.required_fields == package_two.required_fields
    assert package_one.required_artifacts == package_two.required_artifacts
    assert (
        package_one.ledger_record.related_record_id
        == package_two.ledger_record.related_record_id
    )
    assert render_one.checksums == render_two.checksums
    assert (
        render_one.ledger_record.related_record_id
        == render_two.ledger_record.related_record_id
    )
    assert render_one.rendered_paths[0].read_text(encoding="utf-8") == render_two.rendered_paths[
        0
    ].read_text(encoding="utf-8")


def test_replayed_terms_change_and_reconciliation_requests_remain_consistent(
    tmp_path: Path,
) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    seed_opportunity(ledger_service)
    seed_policy_decision(ledger_service)
    seed_tos_legal_check(ledger_service)
    seed_budget_plan(ledger_service)
    first, second = seed_rules_snapshot_pair(
        ledger_service,
        archive_config,
        first_text="Payout is $25.\nAutomation allowed.",
        second_text="Payout is $10.\nAutomation prohibited.",
    )
    monitor = TermsChangeMonitor(archive_config, ledger_service)
    request = TermsChangeMonitorRequest(
        opportunity_id="opp_001",
        prior_rules_text=str(first.ledger_record.payload["normalized_text"]),
        current_rules_text=str(second.ledger_record.payload["normalized_text"]),
        prior_evidence_archive_ids=first.evidence_archive_ids,
        current_evidence_archive_ids=second.evidence_archive_ids,
        prior_budget_plan_id="budget_001",
        prior_tos_legal_check_id="tos_001",
    )

    change_one = monitor.evaluate(request)
    change_two = monitor.evaluate(request)
    reconciliation_request = RevenueReconciliationRequest(
        opportunity_id="opp_001",
        expected_amount=25.0,
        currency_or_asset="USD",
        current_date=datetime(2026, 1, 6, tzinfo=UTC),
        expected_date=datetime(2026, 1, 2, tzinfo=UTC),
        observations=[
            ReconciliationObservation(
                observation_id="obs_001",
                source_type="receipt",
                reference_id="receipt_001",
                amount=10.0,
                currency_or_asset="USD",
                observed_at=datetime(2026, 1, 6, tzinfo=UTC),
            )
        ],
    )
    reconciler = RevenueReconciler(archive_config, ledger_service)
    reconciliation_one = reconciler.reconcile(reconciliation_request)
    reconciliation_two = reconciler.reconcile(reconciliation_request)

    assert change_one.severity == change_two.severity
    assert change_one.changed_fields == change_two.changed_fields
    assert change_one.summary == change_two.summary
    assert change_one.ledger_record.related_record_id == change_two.ledger_record.related_record_id
    assert reconciliation_one.status == reconciliation_two.status
    assert reconciliation_one.reason_codes == reconciliation_two.reason_codes
    assert reconciliation_one.variance == reconciliation_two.variance
    assert (
        reconciliation_one.ledger_record.related_record_id
        == reconciliation_two.ledger_record.related_record_id
    )


def test_replayed_metrics_exports_keep_stable_content_and_metadata(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    seed_realistic_metrics_history(
        ledger_service,
        archive_config,
        opportunity_id="opp_001",
        category="bounty",
        expected_amount=20.0,
        revenue_usd=20.0,
        observed_amount=20.0,
    )
    exporter = make_exporter(tmp_path, archive_config, ledger_service)
    request = MetricsExportRequest(
        export_type="experiment_reviews",
        output_format="json",
        opportunity_category="bounty",
    )

    first = exporter.export(request)
    second = exporter.export(request)

    assert first.summary == second.summary
    assert first.output_path.read_text(encoding="utf-8") == second.output_path.read_text(
        encoding="utf-8"
    )
    assert first.output_path != second.output_path
    assert first.output_path.is_relative_to(tmp_path / "exports") is True
    assert second.output_path.is_relative_to(tmp_path / "exports") is True
