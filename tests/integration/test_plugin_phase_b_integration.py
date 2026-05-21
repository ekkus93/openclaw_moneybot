"""Integration coverage for the PLUGINS1 Phase B wave."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.plugins.artifact_renderer_plugin import (
    ArtifactRendererPlugin,
    ArtifactRenderRequest,
)
from openclaw_moneybot.plugins.deadline_scheduler_plugin import (
    DeadlineQueryRequest,
    DeadlineScheduleRequest,
    DeadlineSchedulerPlugin,
)
from openclaw_moneybot.plugins.download_quarantine_plugin import (
    DownloadQuarantinePlugin,
    QuarantineIngestRequest,
    QuarantinePromoteRequest,
)
from openclaw_moneybot.plugins.opportunity_index_plugin import (
    OpportunityIndexPlugin,
    OpportunitySimilarityQueryRequest,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    ArtifactRendererConfig,
    DeadlineSchedulerConfig,
    DownloadQuarantineConfig,
    Opportunity,
    OpportunityIndexConfig,
)
from openclaw_moneybot.shared.types import RecordType, RiskLevel
from openclaw_moneybot.skills.duplicate_opportunity_detector import (
    DuplicateOpportunityDetector,
    DuplicateOpportunityDetectorRequest,
    OpportunityFingerprint,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.timebox_and_queue_planner import (
    QueueOpportunityItem,
    QueuePlanRequest,
    TimeboxAndQueuePlanner,
)


def test_opportunity_index_can_back_duplicate_reasoning(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Example docs bounty",
            category="bounty",
            status="open",
            source_url="https://example.com/bounty/1",
            required_spend_usd=0,
            estimated_revenue_usd=25,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key="opp:1",
    )
    index = OpportunityIndexPlugin(
        OpportunityIndexConfig(enabled=True, index_path=tmp_path / "opportunity_index.json"),
        ledger_service,
    )
    index.rebuild_index()
    similar = index.query_similar(
        OpportunitySimilarityQueryRequest(
            title="Example docs bounty",
            source_url="https://example.com/bounty/1",
        )
    )
    detector = DuplicateOpportunityDetector(ledger_service)
    result = detector.evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=OpportunityFingerprint(
                opportunity_id="opp_new",
                title="Example docs bounty",
                source_url="https://example.com/bounty/1",
                description="Docs work",
                payout_usd=25,
                platform="example",
            ),
            existing=[
                OpportunityFingerprint(
                    opportunity_id=match.opportunity_id,
                    title="Example docs bounty",
                    source_url="https://example.com/bounty/1",
                    description="Docs work",
                    payout_usd=25,
                    platform="example",
                )
                for match in similar.matches
            ],
        )
    )

    assert result.is_duplicate is True


def test_artifact_renderer_can_render_submission_bundle(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    template_root = tmp_path / "templates"
    template_root.mkdir()
    (template_root / "submission.json").write_text(
        json.dumps(
            {
                "output_filename": "submission.txt",
                "required_fields": ["name", "summary"],
                "body_template": "Name: {name}\nSummary: {summary}\n",
            }
        ),
        encoding="utf-8",
    )
    renderer = ArtifactRendererPlugin(
        ArtifactRendererConfig(
            enabled=True,
            template_root=template_root,
            render_root=tmp_path / "rendered",
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )

    result = renderer.render(
        ArtifactRenderRequest(
            related_record_id="opp_001",
            template_name="submission",
            field_values={"name": "Bot", "summary": "Ready"},
        )
    )

    assert result.manifest_path.exists() is True
    assert result.evidence_archive_ids


def test_deadline_scheduler_can_feed_queue_planning(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    scheduler = DeadlineSchedulerPlugin(
        DeadlineSchedulerConfig(
            enabled=True,
            schedule_path=tmp_path / "deadline_schedule.json",
        ),
        ledger_service,
    )
    scheduler.schedule(
        DeadlineScheduleRequest(
            reference_id="opp_fast",
            deadline_text="2026-01-02",
            current_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    summary = scheduler.summarize(
        DeadlineQueryRequest(current_time=datetime(2026, 1, 1, tzinfo=UTC))
    )
    queue = TimeboxAndQueuePlanner(ledger_service).plan(
        QueuePlanRequest(
            plan_scope_id="queue_scope",
            available_budget_usd=10,
            items=[
                QueueOpportunityItem(
                    opportunity_id="opp_fast",
                    expected_net_revenue_usd=8,
                    timebox_hours=1,
                    deadline_days=1,
                ),
                QueueOpportunityItem(
                    opportunity_id="opp_slow",
                    expected_net_revenue_usd=5,
                    timebox_hours=1,
                    deadline_days=5,
                ),
            ],
        )
    )

    assert summary.upcoming_reference_ids == ["opp_fast"]
    assert queue.items[0]["opportunity_id"] == "opp_fast"


def test_download_quarantine_can_promote_safe_evidence(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    quarantine = DownloadQuarantinePlugin(
        DownloadQuarantineConfig(
            enabled=True,
            quarantine_root=tmp_path / "quarantine",
            allowed_hosts=["example.com"],
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )
    staged = quarantine.ingest(
        QuarantineIngestRequest(
            related_record_id="opp_001",
            file_name="proof.txt",
            content_bytes=b"proof",
            mime_type="text/plain",
            source_url="https://example.com/proof.txt",
        )
    )
    promoted = quarantine.promote(
        QuarantinePromoteRequest(
            scan_id=staged.scan_id,
            related_type=RecordType.OPPORTUNITY,
            related_id="opp_001",
            evidence_type="safe_download",
        )
    )

    assert promoted.promoted_evidence_id is not None
