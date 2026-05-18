from __future__ import annotations

from pydantic import BaseModel


class OpportunityCandidate(BaseModel):
    opportunity_id: str
    opportunity_name: str
    source_url: str
    category: str
    estimated_value_usd: float
    risk_level: str
    description: str
    evidence_url: str | None = None


class OpportunityScoutRequest(BaseModel):
    source_urls: list[str]
    max_results: int = 10


class OpportunityScoutResult(BaseModel):
    opportunities: list[OpportunityCandidate]
    rejected_opportunities: list[OpportunityCandidate]
    total_candidates: int
    total_accepted: int
    total_rejected: int
    risk_summary: dict[str, int]
