from __future__ import annotations

from pydantic import BaseModel


class ExperimentReviewRequest(BaseModel):
    opportunity_id: str
    experiment_id: str
    initial_budget_usd: float
    actual_spend_usd: float
    actual_revenue_usd: float
    tos_legal_check_id: str | None = None
    policy_decision_id: str | None = None
    budget_plan_id: str | None = None


class ExperimentReviewResult(BaseModel):
    experiment_id: str
    decision: str
    risk_level: str
    net_profit_usd: float
    roi_percent: float
    required_records: list[str]
    reasons: list[str]
