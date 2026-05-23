"""Models for end-to-end orchestration."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.skills.account_eligibility_checker import OperatorProfile
from openclaw_moneybot.skills.deliverable_quality_checker import DeliverableArtifact
from openclaw_moneybot.skills.ledger_skill.models import LedgerTimelineEntry
from openclaw_moneybot.skills.opportunity_scout.models import ScoutSourceDocument
from openclaw_moneybot.skills.wallet_governor_client.models import (
    WalletQuoteSkillResult,
    WalletSpendResult,
)


def _default_operator_profile() -> OperatorProfile:
    return OperatorProfile(
        region="united states",
        age_years=30,
        supported_payout_methods=["paypal", "bank_wire"],
        supported_assets=["btc"],
        operating_systems=["linux", "macos", "windows"],
        available_hardware=["gpu"],
        private_infrastructure_available=True,
        repository_history_available=True,
        prior_contribution_tags=["oss"],
        profile_reputation_available=True,
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
    operator_profile: OperatorProfile = Field(default_factory=_default_operator_profile)
    submission_field_values: dict[str, str] = Field(default_factory=dict)
    submission_artifacts: list[DeliverableArtifact] = Field(default_factory=list)
    enforce_duplicate_check: bool = False
    enforce_counterparty_risk_gate: bool = False


class DryRunMissionResult(MoneyBotModel):
    """Output of the orchestrated workflow."""

    mission: str
    selected_opportunity_id: str
    eligibility_id: str | None = None
    duplicate_analysis_id: str | None = None
    initial_policy_decision_id: str | None = None
    tos_legal_check_id: str | None = None
    budget_plan_id: str | None = None
    execution_policy_decision_id: str | None = None
    counterparty_profile_id: str | None = None
    submission_package_id: str | None = None
    deliverable_quality_id: str | None = None
    email_draft_id: str | None = None
    inner_voice_review_ids: list[str] = Field(default_factory=list)
    wallet_quote: WalletQuoteSkillResult | None = None
    wallet_result: WalletSpendResult | None = None
    experiment_review_id: str | None = None
    payout_reconciliation_id: str | None = None
    strategy_summary_id: str | None = None
    evidence_archive_ids: list[str] = Field(default_factory=list)
    timeline: list[LedgerTimelineEntry] = Field(default_factory=list)
    status: str = "completed"
    stop_stage: str | None = None
    stop_reason: str | None = None
    dry_run: bool = True


class ModelDisagreementInterpretation(MoneyBotModel):
    """Deterministic interpretation of a debate/Arbiter outcome."""

    debate_id: str
    final_resolution_source: str
    final_status: str
    stop_stage: str | None = None
    stop_reason: str | None = None
    required_followups: list[str] = Field(default_factory=list)
    transcript_archive_ids: list[str] = Field(default_factory=list)
    arbiter_review_id: str | None = None
