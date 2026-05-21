"""Integration coverage for the INT_TEST2 Phase A workflow paths."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from openclaw_moneybot.orchestration import DryRunMissionRequest
from openclaw_moneybot.plugins.artifact_renderer_plugin import (
    ArtifactRendererPlugin,
    ArtifactRenderRequest,
)
from openclaw_moneybot.plugins.rules_snapshot_gateway import (
    RulesSnapshotCaptureRequest,
    RulesSnapshotGateway,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    ArtifactRendererConfig,
    RulesSnapshotGatewayConfig,
)
from openclaw_moneybot.shared.types import RecordType, TermsChangeSeverity
from openclaw_moneybot.skills.deliverable_quality_checker import DeliverableArtifact
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.submission_package_builder import (
    SubmissionPackageBuilder,
    SubmissionPackageBuildRequest,
)
from openclaw_moneybot.skills.terms_change_monitor import (
    TermsChangeMonitor,
    TermsChangeMonitorRequest,
)

from .helpers import (
    make_archive_config,
    make_orchestrator,
    make_source_document,
    seed_budget_plan,
    seed_opportunity,
    seed_policy_decision,
    seed_tos_legal_check,
)


def make_request(**overrides: object) -> DryRunMissionRequest:
    payload: dict[str, object] = {
        "mission": "INT_TEST2 phase A mission.",
        "source_documents": [
            make_source_document(
                extra_text=(
                    "Required fields: name, email\n"
                    "Attachments: screenshot\n"
                    "Submit at https://example.com/submit\n"
                    "Payout is up to $25."
                )
            )
        ],
        "current_date": datetime(2026, 1, 2, tzinfo=UTC),
    }
    payload.update(overrides)
    return DryRunMissionRequest.model_validate(payload)


def make_renderer(
    tmp_path: Path,
    archive_config: ArchiveConfig,
    ledger_service: LedgerService,
) -> ArtifactRendererPlugin:
    template_root = tmp_path / "templates"
    template_root.mkdir()
    (template_root / "submission.json").write_text(
        json.dumps(
            {
                "output_filename": "submission.txt",
                "required_fields": ["name", "email"],
                "body_template": "Name: {name}\nEmail: {email}\n",
            }
        ),
        encoding="utf-8",
    )
    return ArtifactRendererPlugin(
        ArtifactRendererConfig(
            enabled=True,
            template_root=template_root,
            render_root=tmp_path / "rendered",
        ),
        archive_config,
        ledger_service,
    )


def test_eligibility_eligible_path_records_and_continues(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            draft_recipient_email="maintainer@example.com",
            draft_recipient_name="Maintainer",
            submission_field_values={"name": "Maintainer", "email": "maintainer@example.com"},
            submission_artifacts=[],
        )
    )

    eligibility_events = ledger_service.get_related_events(
        related_type=RecordType.ACCOUNT_ELIGIBILITY,
        related_id=result.eligibility_id or "",
    )

    assert result.status == "failed"
    assert result.stop_stage == "deliverable_quality"
    assert result.eligibility_id is not None
    assert result.initial_policy_decision_id is not None
    assert result.tos_legal_check_id is not None
    assert result.budget_plan_id is not None
    assert ledger_service.get_opportunity(result.selected_opportunity_id) is not None
    assert len(eligibility_events) == 1
    assert eligibility_events[0].payload["related_record_id"] == result.selected_opportunity_id


@pytest.mark.parametrize(
    ("extra_text", "expected_status", "expected_reason"),
    [
        ("Requires W-9 and KYC.", "needs_review", "tax_or_kyc_unverified"),
        ("Account age must be 30 days.", "incomplete", "platform_account_age_unknown"),
    ],
)
def test_eligibility_non_eligible_paths_stop_before_downstream_execution(
    tmp_path: Path,
    extra_text: str,
    expected_status: str,
    expected_reason: str,
) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        make_request(
            source_documents=[make_source_document(extra_text=extra_text)],
            draft_recipient_email="maintainer@example.com",
            draft_recipient_name="Maintainer",
            enable_wallet_payment=True,
        )
    )

    eligibility_events = ledger_service.get_related_events(
        related_type=RecordType.ACCOUNT_ELIGIBILITY,
        related_id=result.eligibility_id or "",
    )

    assert result.status == expected_status
    assert result.stop_stage == "eligibility"
    assert result.stop_reason == expected_reason
    assert result.initial_policy_decision_id is None
    assert result.budget_plan_id is None
    assert result.submission_package_id is None
    assert result.email_draft_id is None
    assert result.wallet_result is None
    assert result.experiment_review_id is None
    assert ledger_service.list_spend_requests_for_opportunity(result.selected_opportunity_id) == []
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []
    assert ledger_service.get_related_events(related_type=RecordType.SUBMISSION_PACKAGE) == []
    assert ledger_service.get_related_events(related_type=RecordType.RENDERED_ARTIFACT) == []
    assert len(eligibility_events) == 1


def test_rules_change_monitor_tracks_no_change_budget_recheck_and_policy_block_paths(
    tmp_path: Path,
) -> None:
    ledger_service = make_orchestrator(tmp_path, spend_enabled=False)[1]
    archive_config = make_archive_config(tmp_path)
    seed_opportunity(ledger_service)
    seed_policy_decision(ledger_service)
    seed_tos_legal_check(ledger_service)
    seed_budget_plan(ledger_service)
    gateway = RulesSnapshotGateway(
        RulesSnapshotGatewayConfig(enabled=True, allowed_hosts=["example.com"]),
        archive_config,
        ledger_service,
    )
    monitor = TermsChangeMonitor(archive_config, ledger_service)
    first = gateway.capture(
        RulesSnapshotCaptureRequest(
            opportunity_id="opp_001",
            source_url="https://example.com/rules",
            content_text="Payout is $25.\nDeadline: 2026-01-02.\nAutomation allowed.",
            content_type="text/plain",
            idempotency_key="rules:first",
        )
    )
    same = gateway.capture(
        RulesSnapshotCaptureRequest(
            opportunity_id="opp_001",
            source_url="https://example.com/rules",
            content_text="Payout is $25.\nDeadline: 2026-01-02.\nAutomation allowed.",
            content_type="text/plain",
            idempotency_key="rules:same",
        )
    )
    changed_budget = gateway.capture(
        RulesSnapshotCaptureRequest(
            opportunity_id="opp_001",
            source_url="https://example.com/rules",
            content_text="Payout is $10.\nDeadline: 2026-02-01.\nAutomation allowed.",
            content_type="text/plain",
            idempotency_key="rules:budget",
        )
    )
    changed_policy = gateway.capture(
        RulesSnapshotCaptureRequest(
            opportunity_id="opp_001",
            source_url="https://example.com/rules",
            content_text=(
                "Payout is $10.\nDeadline: 2026-02-01.\nAutomation prohibited.\nKYC required."
            ),
            content_type="text/plain",
            idempotency_key="rules:policy",
        )
    )

    no_change = monitor.evaluate(
        TermsChangeMonitorRequest(
            opportunity_id="opp_001",
            prior_rules_text=str(first.ledger_record.payload["normalized_text"]),
            current_rules_text=str(same.ledger_record.payload["normalized_text"]),
            prior_evidence_archive_ids=first.evidence_archive_ids,
            current_evidence_archive_ids=same.evidence_archive_ids,
            prior_budget_plan_id="budget_001",
            prior_tos_legal_check_id="tos_001",
        )
    )
    budget_recheck = monitor.evaluate(
        TermsChangeMonitorRequest(
            opportunity_id="opp_001",
            prior_rules_text=str(first.ledger_record.payload["normalized_text"]),
            current_rules_text=str(changed_budget.ledger_record.payload["normalized_text"]),
            prior_evidence_archive_ids=first.evidence_archive_ids,
            current_evidence_archive_ids=changed_budget.evidence_archive_ids,
            prior_budget_plan_id="budget_001",
            prior_tos_legal_check_id="tos_001",
        )
    )
    policy_block = monitor.evaluate(
        TermsChangeMonitorRequest(
            opportunity_id="opp_001",
            prior_rules_text=str(changed_budget.ledger_record.payload["normalized_text"]),
            current_rules_text=str(changed_policy.ledger_record.payload["normalized_text"]),
            prior_evidence_archive_ids=changed_budget.evidence_archive_ids,
            current_evidence_archive_ids=changed_policy.evidence_archive_ids,
            prior_budget_plan_id="budget_001",
            prior_tos_legal_check_id="tos_001",
        )
    )

    assert no_change.change_detected is False
    assert no_change.severity is TermsChangeSeverity.NONE
    assert no_change.requires_budget_recheck is False
    assert no_change.requires_policy_recheck is False
    assert budget_recheck.change_detected is True
    assert budget_recheck.requires_budget_recheck is True
    assert budget_recheck.requires_policy_recheck is False
    assert all(
        ledger_service.get_evidence_record(evidence_id) is not None
        for evidence_id in budget_recheck.evidence_archive_ids
    )
    assert policy_block.severity is TermsChangeSeverity.BLOCK
    assert policy_block.requires_policy_recheck is True
    assert "automation_policy" in policy_block.changed_fields
    assert "kyc_tax_requirement" in policy_block.changed_fields
    assert ledger_service.list_spend_requests_for_opportunity("opp_001") == []
    assert ledger_service.list_email_records_for_opportunity("opp_001") == []
    assert ledger_service.get_related_events(related_type=RecordType.SUBMISSION_PACKAGE) == []
    assert ledger_service.get_related_events(related_type=RecordType.RENDERED_ARTIFACT) == []


def test_submission_package_and_renderer_leave_traceable_chain(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)
    archive_config = make_archive_config(tmp_path)
    result = orchestrator.run_dry_run(
        make_request(
            submission_field_values={"name": "Maintainer", "email": "maintainer@example.com"},
            submission_artifacts=[
                DeliverableArtifact(
                    artifact_name="screenshot",
                    content_text="submission screenshot proof",
                    evidence_archive_id="artifact_001",
                )
            ],
        )
    )
    renderer = make_renderer(tmp_path, archive_config, ledger_service)

    render = renderer.render(
        ArtifactRenderRequest(
            related_record_id=result.selected_opportunity_id,
            template_name="submission",
            field_values={"name": "Maintainer", "email": "maintainer@example.com"},
            evidence_archive_ids=result.evidence_archive_ids,
        )
    )
    package_events = ledger_service.get_related_events(
        related_type=RecordType.SUBMISSION_PACKAGE,
        related_id=result.submission_package_id or "",
    )
    render_events = ledger_service.get_related_events(
        related_type=RecordType.RENDERED_ARTIFACT,
        related_id=render.render_id,
    )
    render_audits = [
        event
        for event in ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)
        if event.payload["related_record_id"] == render.render_id
    ]

    assert result.status == "completed"
    assert result.submission_package_id is not None
    assert result.experiment_review_id is not None
    assert package_events[0].payload["related_record_id"] == result.selected_opportunity_id
    assert render.manifest_path.exists() is True
    assert render.rendered_paths[0].read_text(encoding="utf-8").startswith("Name: Maintainer")
    assert render.checksums["submission.txt"]
    assert render.evidence_archive_ids
    assert render_events[0].payload["related_record_id"] == result.selected_opportunity_id
    assert any(
        isinstance(payload, dict) and payload.get("event_name") == "artifact_rendered"
        for event in render_audits
        for payload in [event.payload.get("payload")]
    )
    assert any(
        isinstance(payload, dict) and payload.get("output_path") == str(render.rendered_paths[0])
        for event in render_audits
        for payload in [event.payload.get("payload")]
    )


def test_submission_package_and_renderer_fail_closed_on_unresolved_or_unknown_inputs(
    tmp_path: Path,
) -> None:
    ledger_service = make_orchestrator(tmp_path, spend_enabled=False)[1]
    archive_config = make_archive_config(tmp_path)
    seed_opportunity(ledger_service)
    seed_policy_decision(ledger_service)
    seed_tos_legal_check(ledger_service)
    seed_budget_plan(ledger_service)
    builder = SubmissionPackageBuilder(archive_config, ledger_service)
    renderer = make_renderer(tmp_path, archive_config, ledger_service)

    package = builder.build(
        SubmissionPackageBuildRequest(
            opportunity_id="opp_001",
            opportunity_name="Integration opportunity",
            rules_text="Required fields. Screenshot required.",
            source_url="https://example.com/submit",
            policy_decision_id="policy_001",
            tos_legal_check_id="tos_001",
            budget_plan_id="budget_001",
        )
    )

    with pytest.raises(ValueError, match="Unknown evidence reference"):
        renderer.render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="submission",
                field_values={"name": "Maintainer", "email": "maintainer@example.com"},
                evidence_archive_ids=["missing_evidence"],
            )
        )

    assert package.status.value == "needs_review"
    assert "required_fields_not_explicit" in package.unresolved_items
    assert ledger_service.get_related_events(related_type=RecordType.RENDERED_ARTIFACT) == []
