from __future__ import annotations

from skills.budget_and_roi_planner.runner import run_budget_plan
from skills.email_drafter.runner import run_email_draft
from skills.experiment_reviewer.runner import run_experiment_review
from skills.moneybot_policy_guard.runner import run_policy_guard
from skills.opportunity_scout.runner import run_opportunity_scout
from skills.receipt_and_evidence_archiver.runner import run_archive
from skills.tos_legal_checker.runner import run_tos_legal_check


def run_integration_pipeline(opportunity_id: str) -> dict:
    scout_result = run_opportunity_scout(opportunity_id)
    tos_result = run_tos_legal_check(opportunity_id)
    policy_result = run_policy_guard(opportunity_id)
    budget_result = run_budget_plan(opportunity_id)
    draft_result = run_email_draft(opportunity_id)
    archive_result = run_archive(opportunity_id)
    review_result = run_experiment_review(opportunity_id)

    return {
        "opportunity_id": opportunity_id,
        "scout_result": scout_result,
        "tos_result": tos_result,
        "policy_result": policy_result,
        "budget_result": budget_result,
        "draft_result": draft_result,
        "archive_result": archive_result,
        "review_result": review_result,
    }
