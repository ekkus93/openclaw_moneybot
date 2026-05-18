from __future__ import annotations

from skills.budget_and_roi_planner.analysis import analyze
from skills.budget_and_roi_planner.models import (
    BudgetPlanRequest,
    BudgetPlanResult,
)


def run_budget_plan(request: BudgetPlanRequest) -> BudgetPlanResult:
    return analyze(request)
