"""Models for queue planning."""

from __future__ import annotations

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class QueueOpportunityItem(MoneyBotModel):
    """One candidate item to prioritize or defer."""

    opportunity_id: str
    expected_net_revenue_usd: float
    timebox_hours: float = Field(gt=0)
    budget_reservation: float = Field(default=0, ge=0)
    deadline_days: int | None = Field(default=None, ge=0)
    review_blocked: bool = False
    recent_failures: int = Field(default=0, ge=0)
    risk_score: int = Field(default=0, ge=0, le=100)


class QueuePlanRequest(MoneyBotModel):
    """Request for deterministic queue planning."""

    plan_scope_id: str
    items: list[QueueOpportunityItem] = Field(default_factory=list)
    available_budget_usd: float = Field(ge=0)
    max_concurrent_experiments: int = Field(default=1, ge=1)
    current_active_experiments: int = Field(default=0, ge=0)


class QueuePlanResult(MoneyBotModel):
    """Structured queue plan."""

    queue_plan_id: str
    items: list[dict[str, str | float]] = Field(default_factory=list)
    ledger_record: LedgerRecord
