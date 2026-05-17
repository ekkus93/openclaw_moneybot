"""Models for the policy guard skill."""

from __future__ import annotations

from pydantic import Field, HttpUrl, JsonValue, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import PolicyDecision
from openclaw_moneybot.shared.types import (
    ActionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RiskLevel,
)


class ExecutionConstraints(MoneyBotModel):
    """Deterministic execution constraints returned by the policy guard."""

    max_spend_usd: float = Field(default=0, ge=0)
    max_email_count: int = Field(default=0, ge=0)
    allowed_domains: list[str] = Field(default_factory=list)
    allowed_wallet_assets: list[str] = Field(default_factory=list)
    allow_public_posting: bool = False
    allow_purchase: bool = False
    allow_wallet_transfer: bool = False


class PolicyCheckRequest(MoneyBotModel):
    """Input request for deterministic policy checks."""

    action_id: str
    action_type: ActionType
    title: str
    description: str
    category: str
    counterparty: str | None = None
    amount_usd: float | None = Field(default=None, ge=0)
    asset: str | None = None
    source_urls: list[HttpUrl] = Field(default_factory=list)
    planned_tools: list[str] = Field(default_factory=list)
    user_approval_present: bool = False
    requires_new_account: bool = False
    requires_payment: bool = False
    requires_email_send: bool = False
    requires_wallet_action: bool = False
    requires_public_claims: bool = False
    requires_user_data_collection: bool = False
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_external_action_fields(self) -> PolicyCheckRequest:
        """Require basic fields for risky external actions."""
        if self.action_type in {
            ActionType.SPEND,
            ActionType.WALLET_TRANSFER,
            ActionType.PURCHASE,
        } and self.amount_usd is None:
            msg = "amount_usd is required for spend and wallet actions"
            raise ValueError(msg)
        return self


class PolicyCheckResult(MoneyBotModel):
    """Full policy-guard output for downstream use."""

    decision: PolicyDecisionType
    risk_level: RiskLevel
    confidence: ConfidenceLevel
    allowed_action_type: str | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    required_mitigations: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    human_review_reason: str | None = None
    safe_next_steps: list[str] = Field(default_factory=list)
    required_followup_skills: list[str] = Field(default_factory=list)
    human_review_required: bool = False
    execution_constraints: ExecutionConstraints = Field(default_factory=ExecutionConstraints)
    notes: str = ""
    ledger_record: PolicyDecision
