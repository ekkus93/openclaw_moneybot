from __future__ import annotations

from pydantic import BaseModel


class BudgetPlanRequest(BaseModel):
    opportunity_id: str
    opportunity_name: str
    tos_legal_check_id: str
    policy_decision_id: str
    proposed_action: str
    required_spend_usd: float
    estimated_revenue_usd: float
    estimated_time_hours: float | None = None
    fees_usd: float
    recurring_costs_usd: float | None = None
    wallet_balance_usd: float
    daily_spend_remaining_usd: float | None = None


class BudgetPlanResult(BaseModel):
    budget_plan_id: str
    decision: str
    recommended_budget_usd: float
    max_loss_usd: float
    expected_gross_revenue_usd: float
    expected_net_revenue_usd: float
    break_even_condition: str | None = None
    success_metric: str
    stop_condition: str
    required_records: list[str]
    risk_level: str
    wallet_spend_request_allowed: bool
    reasons: list[str]
