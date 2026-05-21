"""Models for counterparty risk profiling."""

from __future__ import annotations

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import CounterpartyRiskTier


class CounterpartyRiskProfileRequest(MoneyBotModel):
    """Request for deterministic counterparty risk scoring."""

    opportunity_id: str
    counterparty_name: str
    platform_domain: str | None = None
    payout_history_success_rate: float | None = Field(default=None, ge=0, le=1)
    prior_disputes: int = Field(default=0, ge=0)
    support_responsive: bool | None = None
    clear_payout_rules: bool = False
    clear_deadlines: bool = False
    suspicious_claims_present: bool = False
    off_platform_payment_required: bool = False
    unexpected_kyc_required: bool = False
    domain_age_days: int | None = Field(default=None, ge=0)
    evidence_archive_ids: list[str] = Field(default_factory=list)


class CounterpartyRiskProfileResult(MoneyBotModel):
    """Structured counterparty risk profile."""

    counterparty_profile_id: str
    risk_tier: CounterpartyRiskTier
    score: int = Field(ge=0, le=100)
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    recommended_action: str
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
