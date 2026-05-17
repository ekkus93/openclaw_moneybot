"""Shared contract models."""

from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, Field, HttpUrl, JsonValue, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel, TimestampedModel
from openclaw_moneybot.shared.types import (
    ActionType,
    BudgetDecisionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RecordType,
    ReviewDecisionType,
    RiskLevel,
    TosDecisionType,
)


class MoneyBotAction(MoneyBotModel):
    """A proposed or executed MoneyBot action."""

    action_id: str
    action_type: ActionType
    title: str
    description: str
    category: str
    source_urls: list[HttpUrl] = Field(default_factory=list)
    counterparty: str | None = None
    amount_usd: float | None = Field(default=None, ge=0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Opportunity(TimestampedModel):
    """A discovered opportunity."""

    opportunity_id: str
    name: str
    category: str
    status: str
    source_url: HttpUrl
    rules_url: HttpUrl | None = None
    required_spend_usd: float = Field(default=0, ge=0)
    estimated_revenue_usd: float | None = Field(default=None, ge=0)
    max_loss_usd: float = Field(default=0, ge=0)
    legal_risk_precheck: RiskLevel = RiskLevel.MEDIUM
    tos_risk_precheck: RiskLevel = RiskLevel.MEDIUM
    summary: str | None = None
    raw_json: dict[str, JsonValue] = Field(default_factory=dict)


class PolicyDecision(TimestampedModel):
    """Structured policy decision output."""

    policy_decision_id: str
    decision: PolicyDecisionType
    risk_level: RiskLevel
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    blocked_reasons: list[str] = Field(default_factory=list)
    required_mitigations: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    human_review_reason: str | None = None
    safe_next_steps: list[str] = Field(default_factory=list)
    policy_version: str
    request_fingerprint: str
    expires_at: AwareDatetime | None = None

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware expiry timestamps."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "expires_at must be timezone-aware"
            raise ValueError(msg)
        return value


class TosLegalCheck(TimestampedModel):
    """Structured terms/legal check output."""

    tos_legal_check_id: str
    opportunity_id: str
    decision: TosDecisionType
    confidence: ConfidenceLevel
    platform_terms_summary: str
    legal_risk_summary: str
    tos_risk_summary: str
    red_flags: list[str] = Field(default_factory=list)
    required_mitigations: list[str] = Field(default_factory=list)
    required_records: list[str] = Field(default_factory=list)
    source_quotes_or_snippets: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)


class BudgetPlan(TimestampedModel):
    """Structured budget and ROI planning output."""

    budget_plan_id: str
    opportunity_id: str
    policy_decision_id: str
    tos_legal_check_id: str
    decision: BudgetDecisionType
    recommended_budget_usd: float = Field(ge=0)
    max_loss_usd: float = Field(ge=0)
    expected_gross_revenue_usd: float = Field(ge=0)
    expected_net_revenue_usd: float
    break_even_condition: str
    success_metric: str
    stop_condition: str
    required_records: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    wallet_spend_request_allowed: bool = False
    reasons: list[str] = Field(default_factory=list)


class LedgerRecord(TimestampedModel):
    """A generic ledger event ready for storage."""

    record_id: str
    record_type: RecordType
    related_record_id: str | None = None
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    idempotency_key: str | None = None


class SpendRequest(TimestampedModel):
    """A wallet spend request."""

    spend_request_id: str
    budget_plan_id: str
    policy_decision_id: str
    ledger_record_id: str
    amount_usd: float = Field(gt=0)
    asset: str
    destination: str
    counterparty: str
    purpose: str
    category: str
    evidence_archive_ids: list[str] = Field(default_factory=list)


class EvidenceRecord(TimestampedModel):
    """A stored evidence artifact."""

    evidence_id: str
    related_record_type: RecordType
    related_record_id: str
    evidence_type: str
    archive_path: str
    content_sha256: str
    source_url: HttpUrl | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class EmailDraftRecord(TimestampedModel):
    """A draft email record."""

    email_draft_id: str
    opportunity_id: str | None = None
    related_experiment_id: str | None = None
    to: str
    subject: str
    body: str
    risk_flags: list[str] = Field(default_factory=list)


class ExperimentReview(TimestampedModel):
    """A review of an experiment outcome."""

    experiment_review_id: str
    opportunity_id: str
    spent_usd: float = Field(ge=0)
    revenue_usd: float = Field(ge=0)
    net_usd: float
    roi_percent: float
    outcome: str
    decision: ReviewDecisionType
    lessons: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
