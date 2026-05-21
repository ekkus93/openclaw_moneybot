"""Models for reusable strategy summaries."""

from __future__ import annotations

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import (
    CounterpartyRiskTier,
    ReconciliationStatus,
    StrategyLessonCategory,
)


class StrategyMemorySummaryRequest(MoneyBotModel):
    """Request for deterministic strategy summarization."""

    opportunity_id: str
    experiment_review_id: str
    scope: str
    net_usd: float
    roi_percent: float
    time_spent_hours: float = Field(ge=0)
    reconciliation_status: ReconciliationStatus
    counterparty_risk_tier: CounterpartyRiskTier | None = None
    contradictory_results: bool = False
    evidence_archive_ids: list[str] = Field(default_factory=list)


class StrategyMemorySummaryResult(MoneyBotModel):
    """Structured strategy memory summary."""

    summary_id: str
    scope: str
    lesson_categories: list[StrategyLessonCategory] = Field(default_factory=list)
    what_worked: list[str] = Field(default_factory=list)
    what_failed: list[str] = Field(default_factory=list)
    heuristics_to_keep: list[str] = Field(default_factory=list)
    heuristics_to_avoid: list[str] = Field(default_factory=list)
    tentative_hypotheses: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
