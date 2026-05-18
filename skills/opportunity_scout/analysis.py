from __future__ import annotations

from skills.opportunity_scout.models import (
    OpportunityCandidate,
    OpportunityScoutRequest,
    OpportunityScoutResult,
)

ALLOWED_CATEGORIES = {
    "bounty",
    "coding_challenge",
    "bug_hunt",
    "research_grant",
    "open_source_contribution",
    "technical_writeup",
}

PROHIBITED_CATEGORIES = {
    "gambling",
    "betting",
    "prediction_market",
    "crypto_trading",
    "defi_yield",
    "nft_speculation",
}


def analyze(req: OpportunityScoutRequest) -> OpportunityScoutResult:
    candidates = _extract_candidates(req)
    opportunities = []
    rejected = []
    risk_summary: dict[str, int] = {}

    seen_urls = set()

    for candidate in candidates:
        if candidate.source_url in seen_urls:
            rejected.append(candidate)
            continue
        seen_urls.add(candidate.source_url)

        if candidate.category in PROHIBITED_CATEGORIES:
            rejected.append(candidate)
            continue

        risk_summary[candidate.risk_level] = risk_summary.get(
            candidate.risk_level, 0
        ) + 1

        opportunities.append(candidate)

    return OpportunityScoutResult(
        opportunities=opportunities,
        rejected_opportunities=rejected,
        total_candidates=len(opportunities) + len(rejected),
        total_accepted=len(opportunities),
        total_rejected=len(rejected),
        risk_summary=risk_summary,
    )


def _extract_candidates(req: OpportunityScoutRequest) -> list[OpportunityCandidate]:
    candidates: list[OpportunityCandidate] = []
    for url in req.source_urls:
        candidate = OpportunityCandidate(
            opportunity_id=url,
            opportunity_name=url,
            source_url=url,
            category="unknown",
            estimated_value_usd=0.0,
            risk_level="unknown",
            description="",
        )
        candidates.append(candidate)
    return candidates
