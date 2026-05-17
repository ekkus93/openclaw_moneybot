from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DecisionState(StrEnum):
    allow = "allow"
    block = "block"
    needs_review = "needs_review"


class ActionCategory(StrEnum):
    spend = "spend"
    email_send = "email_send"
    browser_submit = "browser_submit"
    internal = "internal"
    unknown = "unknown"


class BlockedCategory(StrEnum):
    gambling = "gambling"
    trading = "trading"
    spam = "spam"
    deception = "deception"
    illegal_goods = "illegal_goods"
    adult = "adult"
    crypto_trading = "crypto_trading"
    prediction_market = "prediction_market"
    money_transmission = "money_transmission"
    kyc_evasion = "kyc_evasion"


class MoneyBotAction(BaseModel):
    action_id: str
    action_type: ActionCategory
    description: str
    category: str
    counterparty: str | None = None
    amount_usd: float | None = None
    asset: str | None = None
    source_urls: list[str] | None = None
    planned_tools: list[str] | None = None
    user_approval_present: bool = False
    metadata: dict[str, Any] | None = None


class PolicyDecision(BaseModel):
    decision: DecisionState
    risk_level: RiskLevel
    blocked_reasons: list[str]
    required_mitigations: list[str]
    matched_rules: list[str]
    human_review_reason: str | None = None
    safe_next_steps: list[str]
    expires_at: str | None = None


class Opportunity(BaseModel):
    opportunity_id: str
    name: str
    category: str
    source_url: str | None = None
    rules_url: str | None = None
    payment_or_revenue_mechanism: str | None = None
    required_spend_usd: float | None = None
    estimated_revenue_usd: float | None = None
    max_loss_usd: float | None = None
    legal_risk_precheck: str | None = None
    tos_risk_precheck: str | None = None
    evidence_links: list[str] | None = None
    recommended_next_skill: str | None = None


class BudgetPlan(BaseModel):
    budget_plan_id: str
    opportunity_id: str
    tos_legal_check_id: str
    policy_decision_id: str
    proposed_action: str
    required_spend_usd: float
    estimated_revenue_usd: float
    fees_usd: float
    recurring_costs_usd: float
    wallet_balance_usd: float
    daily_spend_remaining_usd: float
    evidence_archive_ids: list[str] | None = None


class SpendRequest(BaseModel):
    spend_request_id: str
    budget_plan_id: str
    policy_decision_id: str
    ledger_event_id: str
    amount_usd: float
    asset: str
    destination: str
    counterparty: str
    purpose: str
    category: str
    evidence_archive_ids: list[str] | None = None


class EvidenceRecord(BaseModel):
    evidence_id: str
    related_type: str
    related_id: str
    evidence_type: str
    source_url: str | None = None
    archive_path: str | None = None
    content_sha256: str | None = None
    created_at: str | None = None


class ExperimentReview(BaseModel):
    experiment_review_id: str
    opportunity_id: str
    spent_usd: float
    revenue_usd: float
    net_usd: float
    roi_percent: float
    time_spent_hours: float | None = None
    success_metric_status: str
    stop_condition_status: str
    lessons: list[str]
    decision: str
    recommended_next_actions: list[str]
    new_blocklist_patterns: list[str]
    scoring_feedback: dict[str, Any] | None = None
