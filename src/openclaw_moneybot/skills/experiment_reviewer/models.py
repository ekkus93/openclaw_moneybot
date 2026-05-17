"""Contracts for experiment review."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import ExperimentReview
from openclaw_moneybot.shared.types import ReviewDecisionType


class ExperimentReviewRequest(MoneyBotModel):
    """Request to review an experiment."""

    opportunity_id: str
    budget_plan_id: str
    review_reason: str
    current_date: datetime
    revenue_usd: float = Field(default=0, ge=0)
    unrealized_value_usd: float = Field(default=0, ge=0)
    fees_usd: float = Field(default=0, ge=0)
    time_spent_hours: float = Field(default=0, ge=0)
    success_metric_met: bool = False
    stop_condition_triggered: bool = False
    evidence_archive_ids: list[str] = Field(default_factory=list)
    incident_flags: list[str] = Field(default_factory=list)
    manual_notes: str = ""


class ExperimentReviewResult(MoneyBotModel):
    """Rich experiment review output."""

    experiment_review_id: str
    opportunity_id: str
    status: str
    spent_usd: float = Field(ge=0)
    revenue_usd: float = Field(ge=0)
    net_usd: float
    roi_percent: float
    time_spent_hours: float = Field(ge=0)
    success_metric_status: str
    stop_condition_status: str
    evidence_quality: str
    lessons: list[str] = Field(default_factory=list)
    decision: ReviewDecisionType
    recommended_next_actions: list[str] = Field(default_factory=list)
    new_blocklist_patterns: list[str] = Field(default_factory=list)
    scoring_feedback: dict[str, str | float] = Field(default_factory=dict)
    budget_feedback: list[str] = Field(default_factory=list)
    policy_feedback: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: ExperimentReview
    reviewer_version: str = "v1"
