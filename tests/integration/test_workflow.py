"""Integration tests for the default workflow."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.orchestration import DryRunMissionRequest
from openclaw_moneybot.shared.types import PolicyDecisionType, RecordType, ReviewDecisionType
from openclaw_moneybot.skills.budget_and_roi_planner import BudgetAndRoiPlanner
from openclaw_moneybot.skills.budget_and_roi_planner.models import (
    BudgetPlanRequest,
    BudgetPlanResult,
)
from openclaw_moneybot.skills.deliverable_quality_checker import DeliverableArtifact
from openclaw_moneybot.skills.experiment_reviewer import ExperimentReviewRequest
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.moneybot_policy_guard import MoneyBotPolicyGuard
from openclaw_moneybot.skills.moneybot_policy_guard.models import (
    PolicyCheckRequest,
    PolicyCheckResult,
)
from openclaw_moneybot.skills.wallet_governor_client.models import (
    WalletLimitCheck,
    WalletQuoteSkillRequest,
    WalletQuoteSkillResult,
    WalletSpendRequest,
    WalletSpendResult,
)

from .helpers import make_orchestrator, make_policy_config, make_source_document


class PolicyGuardWithCategoryOverride:
    """Wrap the policy guard and override category on selected calls."""

    def __init__(
        self,
        policy_guard: MoneyBotPolicyGuard,
        *,
        first_category: str | None = None,
        second_category: str | None = None,
    ) -> None:
        self.policy_guard = policy_guard
        self.first_category = first_category
        self.second_category = second_category
        self.call_count = 0

    def evaluate(self, request: PolicyCheckRequest) -> PolicyCheckResult:
        self.call_count += 1
        updated_request = request
        if self.call_count == 1 and self.first_category is not None:
            updated_request = request.model_copy(update={"category": self.first_category})
        if self.call_count == 2 and self.second_category is not None:
            updated_request = request.model_copy(update={"category": self.second_category})
        return self.policy_guard.evaluate(updated_request)


class BudgetPlannerWithUnknownFees:
    """Wrap the budget planner and force a human-review outcome."""

    def __init__(self, planner: BudgetAndRoiPlanner) -> None:
        self.planner = planner

    def evaluate(self, request: BudgetPlanRequest) -> BudgetPlanResult:
        updated_request = request.model_copy(update={"fees_usd": None})
        return self.planner.evaluate(updated_request)


def make_request(**overrides: object) -> DryRunMissionRequest:
    payload: dict[str, object] = {
        "mission": "Integration workflow mission.",
        "source_documents": [
            make_source_document(extra_text="Requires $5 spend. Payout is up to $25.")
        ],
        "current_date": datetime(2026, 1, 2, tzinfo=UTC),
    }
    payload.update(overrides)
    return DryRunMissionRequest.model_validate(payload)


def test_dry_run_workflow_creates_full_trail(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Review one bounded bounty.",
            draft_recipient_email="maintainer@example.com",
            draft_recipient_name="Maintainer",
            enable_wallet_payment=False,
        )
    )

    event_types = {item.event_type for item in result.timeline}

    assert result.status == "completed"
    assert result.stop_stage is None
    assert result.dry_run is True
    assert result.wallet_quote is not None
    assert result.wallet_result is None
    assert result.email_draft_id is not None
    assert result.experiment_review_id is not None
    assert {
        "opportunity",
        "policy_decision",
        "tos_legal_check",
        "budget_plan",
        "email_draft",
        "experiment_review",
    } <= event_types
    assert result.evidence_archive_ids


def test_initial_policy_block_stops_before_downstream_work(tmp_path: Path) -> None:
    policy_guard = PolicyGuardWithCategoryOverride(
        MoneyBotPolicyGuard(make_policy_config()),
        first_category="gambling",
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=True,
        policy_guard=policy_guard,
    )

    result = orchestrator.run_dry_run(
        make_request(
            mission="Try a blocked category.",
            source_documents=[make_source_document()],
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
        )
    )

    assert result.status == "block"
    assert result.stop_stage == "initial_policy"
    assert result.initial_policy_decision_id is not None
    assert result.tos_legal_check_id is None
    assert result.budget_plan_id is None
    assert result.execution_policy_decision_id is None
    assert result.email_draft_id is None
    assert result.experiment_review_id is None
    assert ledger_service.get_opportunity(result.selected_opportunity_id) is not None
    assert ledger_service.get_policy_decision(result.initial_policy_decision_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )
    assert result.evidence_archive_ids


def test_eligibility_block_stops_before_policy_and_budget(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Reject a personal-account-only opportunity.",
            source_documents=[
                make_source_document(extra_text="Requires personal account and PayPal payout.")
            ],
        )
    )

    assert result.status == "blocked"
    assert result.stop_stage == "eligibility"
    assert result.initial_policy_decision_id is None
    assert result.budget_plan_id is None
    assert result.eligibility_id is not None
    assert ledger_service.get_opportunity(result.selected_opportunity_id) is not None


def test_eligibility_review_stops_safely_before_budget(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Pause for ambiguous KYC requirements.",
            source_documents=[make_source_document(extra_text="Requires KYC tax form.")],
        )
    )

    assert result.status == "needs_review"
    assert result.stop_stage == "eligibility"
    assert result.budget_plan_id is None


def test_initial_policy_needs_review_stops_before_downstream_work(tmp_path: Path) -> None:
    policy_guard = PolicyGuardWithCategoryOverride(
        MoneyBotPolicyGuard(make_policy_config()),
        first_category="affiliate_marketing",
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=False,
        policy_guard=policy_guard,
    )

    result = orchestrator.run_dry_run(
        make_request(
            mission="Try a review-required category.",
            source_documents=[make_source_document()],
        )
    )

    assert result.status == "needs_review"
    assert result.stop_stage == "initial_policy"
    assert result.initial_policy_decision_id is not None
    assert result.tos_legal_check_id is None
    assert result.budget_plan_id is None
    assert result.experiment_review_id is None
    assert ledger_service.get_policy_decision(result.initial_policy_decision_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []


def test_tos_reject_stops_before_budget_and_execution(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Review terms that reject automation.",
            source_documents=[make_source_document(extra_text="Automation prohibited. No bots.")],
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
        )
    )

    assert result.status == "reject"
    assert result.stop_stage == "tos_legal"
    assert result.tos_legal_check_id is not None
    assert result.budget_plan_id is None
    assert result.execution_policy_decision_id is None
    assert result.experiment_review_id is None
    assert ledger_service.get_tos_legal_check(result.tos_legal_check_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )


def test_tos_human_review_stops_before_budget_and_execution(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Review terms needing clarification.",
            source_documents=[make_source_document(extra_text="Identity verification required.")],
        )
    )

    assert result.status == "human_review"
    assert result.stop_stage == "tos_legal"
    assert result.tos_legal_check_id is not None
    assert result.budget_plan_id is None
    assert result.experiment_review_id is None
    assert ledger_service.get_tos_legal_check(result.tos_legal_check_id) is not None


def test_budget_reject_stops_execution_but_still_records_review(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Run a plan that exceeds the remaining budget.",
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
            wallet_balance_usd=100.0,
            daily_spend_remaining_usd=1.0,
        )
    )

    assert result.status == "reject"
    assert result.stop_stage == "budget"
    assert result.budget_plan_id is not None
    assert result.execution_policy_decision_id is None
    assert result.email_draft_id is None
    assert result.wallet_result is None
    assert result.experiment_review_id is not None
    assert ledger_service.get_budget_plan(result.budget_plan_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )


def test_budget_human_review_without_wallet_handoff_allows_non_wallet_review(
    tmp_path: Path,
) -> None:
    planner_ledger = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    budget_planner = BudgetPlannerWithUnknownFees(
        BudgetAndRoiPlanner(make_policy_config(), planner_ledger)
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=False,
        budget_planner=budget_planner,
    )

    result = orchestrator.run_dry_run(make_request(mission="Run a plan with unknown fees."))

    assert result.status == "human_review"
    assert result.stop_stage == "budget"
    assert result.wallet_quote is None
    assert result.wallet_result is None
    assert result.experiment_review_id is not None
    assert ledger_service.get_experiment_review(result.experiment_review_id) is not None


def test_rejected_wallet_quote_prevents_wallet_send(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)
    spend_called = False

    def reject_quote(request: WalletQuoteSkillRequest) -> WalletQuoteSkillResult:
        del request
        return WalletQuoteSkillResult(
            status="rejected",
            asset="BTC",
            reason="destination_invalid",
            amount_usd_estimate=5.0,
            estimated_fee_usd=0.0,
            limit_check=WalletLimitCheck(
                single_spend_ok=False,
                daily_spend_ok=False,
                weekly_spend_ok=False,
                wallet_balance_ok=False,
            ),
            rejection_reasons=["destination_invalid"],
            raw_response={"status": "rejected", "reason": "destination_invalid"},
        )

    def mark_spend(request: WalletSpendRequest) -> WalletSpendResult:
        nonlocal spend_called
        del request
        spend_called = True
        raise AssertionError("wallet send should not be called after a rejected quote")

    orchestrator.wallet_client.quote = reject_quote  # type: ignore[method-assign]
    orchestrator.wallet_client.spend = mark_spend  # type: ignore[method-assign]

    result = orchestrator.run_dry_run(
        make_request(
            mission="Attempt a payment with a rejected quote.",
            enable_wallet_payment=True,
        )
    )

    assert result.wallet_quote is not None
    assert result.wallet_quote.status == "rejected"
    assert result.wallet_result is None
    assert spend_called is False
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )


def test_execution_policy_block_stops_email_and_wallet(tmp_path: Path) -> None:
    policy_guard = PolicyGuardWithCategoryOverride(
        MoneyBotPolicyGuard(make_policy_config()),
        second_category="gambling",
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=True,
        policy_guard=policy_guard,
    )

    result = orchestrator.run_dry_run(
        make_request(
            mission="Block the concrete execution plan.",
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
        )
    )

    assert result.status == "block"
    assert result.stop_stage == "execution_policy"
    assert result.execution_policy_decision_id is not None
    assert result.email_draft_id is None
    assert result.wallet_result is None
    assert result.experiment_review_id is not None
    assert ledger_service.get_policy_decision(result.execution_policy_decision_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )


def test_profitable_workflow_leaves_traceable_review_and_email_artifacts(
    tmp_path: Path,
) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Run one profitable reviewed mission.",
            draft_recipient_email="maintainer@example.com",
            draft_recipient_name="Maintainer",
            enable_wallet_payment=False,
            observed_revenue_usd=30.0,
        )
    )

    assert result.experiment_review_id is not None
    review = ledger_service.get_experiment_review(result.experiment_review_id)
    review_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.EXPERIMENT_REVIEW,
        related_id=result.experiment_review_id,
    )
    snapshot_payload = json.loads(Path(review_evidence[0].archive_path).read_text(encoding="utf-8"))

    assert result.status == "completed"
    assert result.wallet_result is None
    assert result.email_draft_id is not None
    assert review is not None
    assert review.decision is ReviewDecisionType.CONTINUE
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id)
    assert snapshot_payload["wallet_transaction_ids"] == []
    assert result.email_draft_id in snapshot_payload["email_draft_ids"]


def test_approved_workflow_produces_submission_package_and_reconciliation(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            source_documents=[
                make_source_document(
                    extra_text=(
                        "Required fields: name, email\n"
                        "Attachments: screenshot\n"
                        "Submit at https://example.com/submit\n"
                        "Deadline: 2026-01-05"
                    )
                )
            ],
            submission_field_values={"name": "Maintainer", "email": "maintainer@example.com"},
            submission_artifacts=[
                DeliverableArtifact(
                    artifact_name="screenshot",
                    content_text="real screenshot evidence",
                    evidence_archive_id="artifact_manual",
                )
            ],
            observed_revenue_usd=25.0,
        )
    )

    assert result.status == "completed"
    assert result.submission_package_id is not None
    assert result.deliverable_quality_id is not None
    assert result.payout_reconciliation_id is not None
    assert result.strategy_summary_id is not None


def test_execution_stops_when_submission_package_has_unresolved_items(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            source_documents=[
                make_source_document(
                    extra_text="Please complete the required fields before submitting."
                )
            ]
        )
    )

    assert result.status == "needs_review"
    assert result.stop_stage == "submission_package"
    assert result.submission_package_id is not None
    assert result.experiment_review_id is not None
    assert ledger_service.get_experiment_review(result.experiment_review_id) is not None


def test_missing_payout_creates_reconciliation_and_review_linkage(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(make_request())

    assert result.payout_reconciliation_id is not None
    assert result.experiment_review_id is not None
    assert result.status == "completed"


def test_followup_review_of_costly_execution_with_missing_evidence_requires_human_review(
    tmp_path: Path,
) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)
    workflow_result = orchestrator.run_dry_run(
        make_request(
            mission="Run one costly ambiguous mission.",
            enable_wallet_payment=True,
            observed_revenue_usd=0.0,
        )
    )
    assert workflow_result.budget_plan_id is not None

    review_result = orchestrator.reviewer.review(
        ExperimentReviewRequest(
            opportunity_id=workflow_result.selected_opportunity_id,
            budget_plan_id=workflow_result.budget_plan_id,
            review_reason="followup_missing_evidence",
            current_date=datetime(2026, 1, 3, tzinfo=UTC),
            revenue_usd=0.0,
            time_spent_hours=2.0,
            success_metric_met=False,
            stop_condition_triggered=False,
            evidence_archive_ids=[],
        )
    )
    review_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.EXPERIMENT_REVIEW,
        related_id=review_result.experiment_review_id,
    )
    snapshot_payload = json.loads(Path(review_evidence[0].archive_path).read_text(encoding="utf-8"))

    assert review_result.decision is ReviewDecisionType.HUMAN_REVIEW
    assert snapshot_payload["spend_request_ids"]
    assert snapshot_payload["wallet_transaction_ids"]


def test_followup_review_of_incident_flagged_execution_stops(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=True)
    workflow_result = orchestrator.run_dry_run(
        make_request(
            mission="Run one incident-flagged mission.",
            enable_wallet_payment=True,
            observed_revenue_usd=0.0,
        )
    )
    assert workflow_result.budget_plan_id is not None

    review_result = orchestrator.reviewer.review(
        ExperimentReviewRequest(
            opportunity_id=workflow_result.selected_opportunity_id,
            budget_plan_id=workflow_result.budget_plan_id,
            review_reason="followup_incident",
            current_date=datetime(2026, 1, 3, tzinfo=UTC),
            revenue_usd=0.0,
            time_spent_hours=2.0,
            success_metric_met=False,
            stop_condition_triggered=True,
            evidence_archive_ids=workflow_result.evidence_archive_ids,
            incident_flags=["legal_red_flag"],
        )
    )

    assert review_result.decision is ReviewDecisionType.STOP


def test_execution_policy_needs_review_stops_email_and_wallet(tmp_path: Path) -> None:
    policy_guard = PolicyGuardWithCategoryOverride(
        MoneyBotPolicyGuard(make_policy_config()),
        second_category="affiliate_marketing",
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=True,
        policy_guard=policy_guard,
    )

    result = orchestrator.run_dry_run(
        make_request(
            mission="Require review for the concrete execution plan.",
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
        )
    )

    assert result.status == PolicyDecisionType.NEEDS_REVIEW.value
    assert result.stop_stage == "execution_policy"
    assert result.execution_policy_decision_id is not None
    assert result.email_draft_id is None
    assert result.wallet_result is None
    assert result.experiment_review_id is not None
    assert ledger_service.get_policy_decision(result.execution_policy_decision_id) is not None


def test_wallet_fail_closed_case_is_rejected(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(mission="Attempt a small approved payment.", enable_wallet_payment=True)
    )

    event_types = {item.event_type for item in result.timeline}

    assert result.wallet_result is not None
    assert result.wallet_result.status == "rejected"
    assert "wallet_transaction" not in event_types


def test_tiny_capped_payment_path_succeeds(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        make_request(mission="Run a tiny capped payment path.", enable_wallet_payment=True)
    )

    event_types = {item.event_type for item in result.timeline}

    assert result.wallet_result is not None
    assert result.wallet_result.status == "sent"
    assert "wallet_transaction" in event_types
