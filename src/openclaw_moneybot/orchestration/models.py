"""Models for end-to-end orchestration."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.skills.ledger_skill.models import LedgerTimelineEntry
from openclaw_moneybot.skills.opportunity_scout.models import ScoutSourceDocument
from openclaw_moneybot.skills.wallet_governor_client.models import (
    WalletQuoteSkillResult,
    WalletSpendResult,
)


class DryRunMissionRequest(MoneyBotModel):
    """Request for the default dry-run workflow."""

    mission: str
    source_documents: list[ScoutSourceDocument] = Field(default_factory=list)
    wallet_balance_usd: float = Field(default=100, ge=0)
    daily_spend_remaining_usd: float = Field(default=20, ge=0)
    btc_usd_rate: float = Field(default=50_000, gt=0)
    draft_recipient_email: str | None = None
    draft_recipient_name: str | None = None
    payment_destination: str = "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2"
    payment_counterparty: str = "Example Counterparty"
    payment_purpose: str = "Approved small payment"
    enable_wallet_payment: bool = False
    observed_revenue_usd: float = Field(default=0, ge=0)
    time_spent_hours: float = Field(default=1, ge=0)
    current_date: datetime


class DryRunMissionResult(MoneyBotModel):
    """Output of the orchestrated workflow."""

    mission: str
    selected_opportunity_id: str
    initial_policy_decision_id: str
    tos_legal_check_id: str | None = None
    budget_plan_id: str | None = None
    execution_policy_decision_id: str | None = None
    email_draft_id: str | None = None
    wallet_quote: WalletQuoteSkillResult | None = None
    wallet_result: WalletSpendResult | None = None
    experiment_review_id: str | None = None
    evidence_archive_ids: list[str] = Field(default_factory=list)
    timeline: list[LedgerTimelineEntry] = Field(default_factory=list)
    status: str = "completed"
    stop_stage: str | None = None
    stop_reason: str | None = None
    dry_run: bool = True
