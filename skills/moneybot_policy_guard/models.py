from __future__ import annotations

from pydantic import BaseModel


class PolicyCheckRequest(BaseModel):
    action_id: str
    action_type: str
    description: str
    category: str
    counterparty: str | None = None
    amount_usd: float | None = None
    asset: str | None = None
    source_urls: list[str] | None = None
    planned_tools: list[str] | None = None
    user_approval_present: bool = False
    metadata: dict | None = None


class PolicyDecision(BaseModel):
    policy_decision_id: str
    decision: str
    risk_level: str
    blocked_reasons: list[str]
    required_mitigations: list[str]
    matched_rules: list[str]
    human_review_reason: str | None = None
    safe_next_steps: list[str]
    expires_at: str | None = None
