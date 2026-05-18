"""Models for budget and ROI planning."""

from __future__ import annotations

from pydantic import Field, JsonValue, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import BudgetPlan


class BudgetPlanRequest(MoneyBotModel):
    """Request to turn a vetted opportunity into a bounded plan."""

    opportunity_id: str
    opportunity_name: str
    tos_legal_check_id: str | None
    tos_legal_decision: str | None = None
    policy_decision_id: str | None
    policy_decision: str | None = None
    proposed_action: str
    required_spend_usd: float = Field(ge=0)
    max_loss_usd: float = Field(ge=0)
    estimated_revenue_usd: float | None = Field(default=None, ge=0)
    expected_revenue_unknown: bool = False
    estimated_time_hours: float = Field(ge=0)
    fees_usd: float | None = Field(default=0, ge=0)
    platform_fees_usd: float | None = Field(default=0, ge=0)
    wallet_fee_usd: float | None = Field(default=0, ge=0)
    recurring_costs_usd: float | None = Field(default=0, ge=0)
    recurring_cost_cap_usd: float | None = Field(default=None, ge=0)
    asset: str = "BTC"
    wallet_balance_usd: float = Field(ge=0)
    daily_spend_remaining_usd: float = Field(ge=0)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    approved_spend_categories: list[str] = Field(default_factory=lambda: ["purchase"])
    success_metric: str
    stop_condition: str
    timebox_hours: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_prerequisites(self) -> BudgetPlanRequest:
        """Require explicit planning inputs."""
        if not self.success_metric:
            msg = "success_metric is required."
            raise ValueError(msg)
        if not self.stop_condition:
            msg = "stop_condition is required."
            raise ValueError(msg)
        if self.estimated_revenue_usd is None and not self.expected_revenue_unknown:
            msg = "estimated_revenue_usd is required unless expected_revenue_unknown is true."
            raise ValueError(msg)
        return self


class BudgetPlanResult(MoneyBotModel):
    """Full planner output."""

    budget_plan: BudgetPlan
    wallet_handoff: dict[str, JsonValue] | None = None
