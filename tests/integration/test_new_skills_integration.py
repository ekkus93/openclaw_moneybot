"""Integration coverage for the newer skill wave."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.orchestration import DryRunMissionRequest
from openclaw_moneybot.shared.types import (
    CounterpartyRiskTier,
    PayoutFollowupRecommendation,
    ReconciliationStatus,
)
from openclaw_moneybot.skills.experiment_reviewer import ExperimentReviewRequest
from openclaw_moneybot.skills.payout_followup_planner import (
    PayoutFollowupPlanner,
    PayoutFollowupPlanRequest,
)
from openclaw_moneybot.skills.revenue_reconciler import RevenueReconciliationRequest
from openclaw_moneybot.skills.timebox_and_queue_planner import (
    QueueOpportunityItem,
    QueuePlanRequest,
    TimeboxAndQueuePlanner,
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


def test_high_risk_counterparty_blocks_when_configured(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        DryRunMissionRequest.model_validate(
            {
                "mission": "High-risk counterparty gate",
                "source_documents": [
                    make_source_document(
                        extra_text="Off-platform payment required. suspicious claims. KYC required."
                    )
                ],
                "current_date": datetime(2026, 1, 2, tzinfo=UTC),
                "enforce_counterparty_risk_gate": True,
                "operator_profile": {
                    "tax_identity_available": True,
                    "supported_assets": ["btc"],
                },
            }
        )
    )

    assert result.stop_stage == "counterparty_risk"
    assert result.counterparty_profile_id is not None


def test_duplicate_check_blocks_duplicate_active_opportunity(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)
    seed_opportunity(
        ledger_service,
        source_url="https://example.com/bounty",
        rules_url="https://example.com/bounty/rules",
    )

    result = orchestrator.run_dry_run(
        DryRunMissionRequest.model_validate(
            {
                "mission": "Duplicate bounty",
                "source_documents": [make_source_document()],
                "current_date": datetime(2026, 1, 2, tzinfo=UTC),
                "enforce_duplicate_check": True,
            }
        )
    )

    assert result.stop_stage == "duplicate_check"
    assert len(ledger_service.list_opportunities()) == 1


def test_queue_plan_can_drive_selection_without_bypassing_other_gates(tmp_path: Path) -> None:
    planner = TimeboxAndQueuePlanner(
        ledger_service=make_orchestrator(tmp_path, spend_enabled=False)[1]
    )
    queue = planner.plan(
        QueuePlanRequest(
            plan_scope_id="queue_scope",
            available_budget_usd=20,
            items=[
                QueueOpportunityItem(
                    opportunity_id="opp_fast",
                    expected_net_revenue_usd=10,
                    timebox_hours=1,
                    deadline_days=1,
                ),
                QueueOpportunityItem(
                    opportunity_id="opp_slow",
                    expected_net_revenue_usd=8,
                    timebox_hours=2,
                    deadline_days=10,
                ),
            ],
        )
    )

    assert queue.items[0]["opportunity_id"] == "opp_fast"


def test_deliverable_quality_failure_halts_workflow(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        DryRunMissionRequest.model_validate(
            {
                "mission": "Missing screenshot",
                "source_documents": [
                    make_source_document(
                        extra_text=(
                            "Required fields: name, email\n"
                            "Attachments: screenshot\n"
                            "Submit at https://example.com/submit"
                        )
                    )
                ],
                "submission_field_values": {
                    "name": "Maintainer",
                    "email": "maintainer@example.com",
                },
                "current_date": datetime(2026, 1, 2, tzinfo=UTC),
            }
        )
    )

    assert result.stop_stage == "deliverable_quality"
    assert result.deliverable_quality_id is not None


def test_reconciliation_can_feed_followup_planning_and_review(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)
    archive_config = make_archive_config(tmp_path)
    opportunity = seed_opportunity(ledger_service)
    policy = seed_policy_decision(ledger_service, opportunity_id=opportunity.opportunity_id)
    tos = seed_tos_legal_check(ledger_service, opportunity_id=opportunity.opportunity_id)
    budget = seed_budget_plan(
        ledger_service,
        opportunity_id=opportunity.opportunity_id,
        policy_decision_id=policy.policy_decision_id,
        tos_legal_check_id=tos.tos_legal_check_id,
    )

    reconciliation = orchestrator.revenue_reconciler.reconcile(
        RevenueReconciliationRequest(
            opportunity_id=opportunity.opportunity_id,
            expected_amount=25.0,
            currency_or_asset="USD",
            current_date=datetime(2026, 1, 5, tzinfo=UTC),
            expected_date=datetime(2026, 1, 2, tzinfo=UTC),
            observations=[],
        )
    )
    followup = PayoutFollowupPlanner(archive_config, ledger_service).plan(
        PayoutFollowupPlanRequest(
            opportunity_id=opportunity.opportunity_id,
            reconciliation_status=reconciliation.status,
            has_supporting_evidence=False,
            counterparty_risk_tier=CounterpartyRiskTier.MEDIUM,
            days_since_expected=3,
        )
    )
    review = orchestrator.reviewer.review(
        ExperimentReviewRequest(
            opportunity_id=opportunity.opportunity_id,
            budget_plan_id=budget.budget_plan_id,
            review_reason="followup_chain",
            current_date=datetime(2026, 1, 5, tzinfo=UTC),
            revenue_usd=0.0,
            time_spent_hours=1.0,
            success_metric_met=False,
            stop_condition_triggered=False,
            incident_flags=[f"payout_{reconciliation.status.value}"],
        )
    )

    assert reconciliation.status is ReconciliationStatus.LATE
    assert followup.recommendation is PayoutFollowupRecommendation.GATHER_MISSING_PROOF
    assert review.experiment_review_id is not None


def test_completed_pipeline_emits_strategy_summary(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        DryRunMissionRequest.model_validate(
            {
                "mission": "Strategy summary pipeline",
                "source_documents": [make_source_document()],
                "current_date": datetime(2026, 1, 2, tzinfo=UTC),
            }
        )
    )

    assert result.strategy_summary_id is not None
