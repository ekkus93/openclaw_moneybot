"""Models for opportunity scouting."""

from __future__ import annotations

from pydantic import Field, HttpUrl, JsonValue, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import Opportunity
from openclaw_moneybot.shared.types import ConfidenceLevel, RiskLevel


class ScoutSourceDocument(MoneyBotModel):
    """A local source document used for fixture-driven scouting."""

    source_name: str
    category_hint: str
    source_url: HttpUrl
    rules_url: HttpUrl | None = None
    payment_method: str
    content_text: str
    known_risk_notes: list[str] = Field(default_factory=list)


class OpportunityScoutRequest(MoneyBotModel):
    """Request for the opportunity scout."""

    mission: str
    budget_usd: float = Field(default=100, ge=0, le=100)
    skills_available: list[str] = Field(default_factory=list)
    blocked_categories: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    max_results: int = Field(default=10, ge=1, le=50)
    time_budget_hours: float = Field(default=8, gt=0)
    evidence_required: bool = True
    source_documents: list[ScoutSourceDocument] = Field(default_factory=list)


class OpportunityCandidate(MoneyBotModel):
    """A ranked opportunity candidate."""

    opportunity_id: str
    name: str
    category: str
    source_url: HttpUrl
    rules_url: HttpUrl | None = None
    payment_or_revenue_mechanism: str
    required_spend_usd: float = Field(ge=0)
    estimated_revenue_low_usd: float = Field(ge=0)
    estimated_revenue_high_usd: float = Field(ge=0)
    estimated_time_hours: float = Field(ge=0)
    time_to_first_dollar_days: float = Field(ge=0)
    max_loss_usd: float = Field(ge=0)
    skill_fit: ConfidenceLevel
    legal_risk: RiskLevel
    tos_risk: RiskLevel
    operational_complexity: ConfidenceLevel
    blocked_flags: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    why_this_is_legitimate: str
    recommended_next_step: str
    confidence: ConfidenceLevel
    evidence_links: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    tos_handoff: dict[str, JsonValue]
    ledger_record: Opportunity


class RejectedCandidate(MoneyBotModel):
    """A rejected source candidate."""

    name: str
    source_url: HttpUrl | None = None
    rejection_reason: str


class OpportunityScoutResult(MoneyBotModel):
    """Full scout result."""

    mission: str
    generated_at: str
    summary: str
    candidates_reviewed: int = Field(ge=0)
    candidates_rejected: int = Field(ge=0)
    opportunities: list[OpportunityCandidate] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidate] = Field(default_factory=list)
    top_recommendations: list[str] = Field(default_factory=list)
    search_summary: str
    source_coverage: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_top_recommendations(self) -> OpportunityScoutResult:
        """Ensure top recommendations refer to returned opportunities."""
        valid_ids = {candidate.opportunity_id for candidate in self.opportunities}
        for opportunity_id in self.top_recommendations:
            if opportunity_id not in valid_ids:
                msg = f"top recommendation '{opportunity_id}' is not in opportunities"
                raise ValueError(msg)
        return self
