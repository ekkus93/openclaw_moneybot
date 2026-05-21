"""Models for payout follow-up planning."""

from __future__ import annotations

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import (
    CounterpartyRiskTier,
    PayoutFollowupRecommendation,
    ReconciliationStatus,
)


class PayoutFollowupPlanRequest(MoneyBotModel):
    """Request for safe payout follow-up recommendations."""

    opportunity_id: str
    reconciliation_status: ReconciliationStatus
    has_supporting_evidence: bool
    counterparty_risk_tier: CounterpartyRiskTier = CounterpartyRiskTier.MEDIUM
    terms_ambiguous: bool = False
    days_since_expected: int = Field(default=0, ge=0)
    grace_period_days: int = Field(default=3, ge=0)
    evidence_archive_ids: list[str] = Field(default_factory=list)


class PayoutFollowupPlanResult(MoneyBotModel):
    """Structured payout follow-up plan."""

    followup_plan_id: str
    recommendation: PayoutFollowupRecommendation
    draft_needed: bool
    suggested_message_purpose: str | None = None
    required_supporting_evidence: list[str] = Field(default_factory=list)
    timing_recommendation: str
    stop_conditions: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
