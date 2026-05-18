from __future__ import annotations

from pydantic import BaseModel


class TosLegalCheckRequest(BaseModel):
    opportunity_id: str
    opportunity_name: str
    source_url: str | None = None
    rules_url: str | None = None
    proposed_action: str
    platform_name: str | None = None
    counterparty: str | None = None
    spend_amount_usd: float | None = None
    expected_revenue_usd: float | None = None
    evidence_text: str | None = None
    evidence_archive_ids: list[str] | None = None


class TosLegalCheckResult(BaseModel):
    tos_check_id: str
    decision: str
    confidence: str
    platform_terms_summary: str | None = None
    legal_risk_summary: str | None = None
    tos_risk_summary: str | None = None
    red_flags: list[str]
    required_mitigations: list[str]
    required_records: list[str]
    source_quotes_or_snippets: list[str] | None = None
    evidence_archive_ids: list[str] | None = None
    handoff_to_policy_guard: dict | None = None
