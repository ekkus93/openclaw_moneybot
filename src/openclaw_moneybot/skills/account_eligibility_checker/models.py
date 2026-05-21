"""Models for account-eligibility checking."""

from __future__ import annotations

from pydantic import Field, HttpUrl

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import ConfidenceLevel, EligibilityDecisionType


class OperatorProfile(MoneyBotModel):
    """Bounded operator capability/profile data allowed in eligibility checks."""

    region: str | None = None
    age_years: int | None = Field(default=None, ge=0)
    residency: str | None = None
    citizenship: str | None = None
    has_business_entity: bool | None = None
    tax_identity_available: bool | None = None
    supported_payout_methods: list[str] = Field(default_factory=list)
    supported_assets: list[str] = Field(default_factory=list)
    operating_systems: list[str] = Field(default_factory=list)
    available_hardware: list[str] = Field(default_factory=list)
    private_infrastructure_available: bool | None = None
    repository_history_available: bool | None = None
    prior_contribution_tags: list[str] = Field(default_factory=list)
    non_bot_social_identity_available: bool = False
    personal_account_allowed: bool = False
    platform_account_age_days: int | None = Field(default=None, ge=0)
    profile_reputation_available: bool | None = None


class AccountEligibilityRequest(MoneyBotModel):
    """Request for deterministic account-eligibility evaluation."""

    opportunity_id: str
    opportunity_name: str
    rules_text: str | None = None
    source_url: HttpUrl | None = None
    policy_decision_id: str | None = None
    tos_legal_check_id: str | None = None
    operator_profile: OperatorProfile = Field(default_factory=OperatorProfile)
    payment_method_hint: str | None = None
    asset_hint: str | None = None
    experiment_constraints: dict[str, str | float | bool] = Field(default_factory=dict)
    evidence_archive_ids: list[str] = Field(default_factory=list)


class AccountEligibilityResult(MoneyBotModel):
    """Structured account-eligibility result."""

    eligibility_id: str
    decision: EligibilityDecisionType
    confidence: ConfidenceLevel
    reasons: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    blocked_requirements: list[str] = Field(default_factory=list)
    review_required_requirements: list[str] = Field(default_factory=list)
    safe_next_steps: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
