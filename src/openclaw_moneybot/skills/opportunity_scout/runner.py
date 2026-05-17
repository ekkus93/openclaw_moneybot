"""Research-only opportunity scout implementation."""

from __future__ import annotations

import re

from pydantic import JsonValue

from openclaw_moneybot.shared import Opportunity
from openclaw_moneybot.shared.types import ConfidenceLevel, RiskLevel
from openclaw_moneybot.skills.opportunity_scout.dedupe import dedupe_candidates
from openclaw_moneybot.skills.opportunity_scout.models import (
    OpportunityCandidate,
    OpportunityScoutRequest,
    OpportunityScoutResult,
    RejectedCandidate,
    ScoutSourceDocument,
)
from openclaw_moneybot.skills.opportunity_scout.scoring import score_candidate
from openclaw_moneybot.skills.opportunity_scout.sources import UNSUPPORTED_SOURCE_CATEGORIES
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now

PROHIBITED_PATTERNS = {
    "trading": "trading_or_speculation",
    "crypto trading": "trading_or_speculation",
    "gambling": "gambling_or_prediction_market",
    "prediction market": "gambling_or_prediction_market",
    "fake account": "fake_accounts",
    "kyc evasion": "kyc_evasion",
    "spam": "spam_outreach",
    "bulk dm": "spam_outreach",
    "other people's funds": "handling_other_peoples_funds",
    "malware": "malware_or_exploit",
    "exploit": "malware_or_exploit",
}


def _extract_money_value(content: str, default: float) -> float:
    match = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", content)
    return float(match.group(1)) if match else default


def _extract_money_values(content: str) -> list[float]:
    return [float(match) for match in re.findall(r"\$([0-9]+(?:\.[0-9]+)?)", content)]


def _contains(content: str, needle: str) -> bool:
    return needle in content.lower()


def _estimate_hours(document: ScoutSourceDocument) -> float:
    text = document.content_text.lower()
    if "quick" in text or "small task" in text:
        return 2.0
    if "hackathon" in text or "contest" in text:
        return 12.0
    return 4.0


def _candidate_from_document(
    request: OpportunityScoutRequest,
    document: ScoutSourceDocument,
) -> OpportunityCandidate | RejectedCandidate:
    category = document.category_hint.strip().lower().replace(" ", "_")
    text = document.content_text.lower()
    if category in UNSUPPORTED_SOURCE_CATEGORIES:
        return RejectedCandidate(
            name=document.source_name,
            source_url=document.source_url,
            rejection_reason=f"Unsupported category: {category}.",
        )
    if category in {value.lower().replace(" ", "_") for value in request.blocked_categories}:
        return RejectedCandidate(
            name=document.source_name,
            source_url=document.source_url,
            rejection_reason=f"Blocked by mission category filter: {category}.",
        )
    for pattern, reason in PROHIBITED_PATTERNS.items():
        if _contains(text, pattern):
            return RejectedCandidate(
                name=document.source_name,
                source_url=document.source_url,
                rejection_reason=reason,
            )

    money_values = _extract_money_values(text)
    required_spend = _extract_money_value(text, 0.0) if "spend" in text else 0.0
    estimated_revenue_low = money_values[0] if money_values else 25.0
    estimated_revenue_high = max(money_values) if money_values else estimated_revenue_low
    estimated_time_hours = _estimate_hours(document)
    max_loss_usd = required_spend
    has_rules = document.rules_url is not None
    skill_fit = (
        ConfidenceLevel.HIGH
        if any(skill in text for skill in request.skills_available)
        else ConfidenceLevel.MEDIUM
    )
    legal_risk = RiskLevel.MEDIUM if category == "affiliate" else RiskLevel.LOW
    tos_risk = RiskLevel.MEDIUM if not has_rules or category == "affiliate" else RiskLevel.LOW
    operational_complexity = (
        ConfidenceLevel.HIGH if category == "contest" else ConfidenceLevel.MEDIUM
    )
    legitimacy = (
        "The source includes a named opportunity, a payout model, and a reviewable source URL."
    )
    next_step = "run_tos_check" if has_rules else "research_more"
    score_breakdown = score_candidate(
        estimated_revenue_high_usd=estimated_revenue_high,
        required_spend_usd=required_spend,
        max_loss_usd=max_loss_usd,
        estimated_time_hours=estimated_time_hours,
        skill_fit=skill_fit,
        legal_risk=legal_risk,
        tos_risk=tos_risk,
        operational_complexity=operational_complexity,
        has_rules_url=has_rules,
        has_evidence=bool(document.content_text),
    )
    opportunity_id = make_id("opp")
    ledger_record = Opportunity(
        created_at=utc_now(),
        opportunity_id=opportunity_id,
        name=document.source_name,
        category=category,
        status="unverified",
        source_url=document.source_url,
        rules_url=document.rules_url,
        required_spend_usd=required_spend,
        estimated_revenue_usd=estimated_revenue_high,
        max_loss_usd=max_loss_usd,
        legal_risk_precheck=legal_risk,
        tos_risk_precheck=tos_risk,
        summary=document.content_text[:200],
        raw_json={"source_name": document.source_name, "payment_method": document.payment_method},
    )
    tos_handoff: dict[str, JsonValue] = {
        "opportunity_id": opportunity_id,
        "opportunity_name": document.source_name,
        "source_url": str(document.source_url),
        "rules_url": None if document.rules_url is None else str(document.rules_url),
        "proposed_action": f"Review the {category} opportunity before execution.",
        "platform_name": document.source_name,
        "counterparty": document.source_name,
        "spend_amount_usd": required_spend,
        "expected_revenue_usd": estimated_revenue_high,
        "evidence_text": document.content_text,
        "evidence_archive_ids": [],
    }
    return OpportunityCandidate(
        opportunity_id=opportunity_id,
        name=document.source_name,
        category=category,
        source_url=document.source_url,
        rules_url=document.rules_url,
        payment_or_revenue_mechanism=document.payment_method,
        required_spend_usd=required_spend,
        estimated_revenue_low_usd=estimated_revenue_low,
        estimated_revenue_high_usd=estimated_revenue_high,
        estimated_time_hours=estimated_time_hours,
        time_to_first_dollar_days=1.0 if category in {"bounty", "documentation"} else 3.0,
        max_loss_usd=max_loss_usd,
        skill_fit=skill_fit,
        legal_risk=legal_risk,
        tos_risk=tos_risk,
        operational_complexity=operational_complexity,
        blocked_flags=[],
        red_flags=document.known_risk_notes,
        why_this_is_legitimate=legitimacy,
        recommended_next_step=next_step,
        confidence=ConfidenceLevel.MEDIUM if has_rules else ConfidenceLevel.LOW,
        evidence_links=[str(document.source_url)],
        score_breakdown=score_breakdown,
        tos_handoff=tos_handoff,
        ledger_record=ledger_record,
    )


class OpportunityScout:
    """Research-only deterministic opportunity scout."""

    def evaluate(self, request: OpportunityScoutRequest) -> OpportunityScoutResult:
        """Return ranked candidates from local source documents."""
        candidates: list[OpportunityCandidate] = []
        rejected: list[RejectedCandidate] = []
        for document in request.source_documents:
            result = _candidate_from_document(request, document)
            if isinstance(result, RejectedCandidate):
                rejected.append(result)
            else:
                candidates.append(result)

        deduped = dedupe_candidates(candidates)
        ranked = sorted(
            deduped,
            key=lambda candidate: candidate.score_breakdown.get("total", 0.0),
            reverse=True,
        )[: request.max_results]
        top_recommendations = [candidate.opportunity_id for candidate in ranked[:3]]
        source_coverage = sorted({document.source_name for document in request.source_documents})
        summary = (
            f"Reviewed {len(request.source_documents)} local source documents, "
            f"kept {len(ranked)} candidates, rejected {len(rejected)}."
        )
        next_actions = [
            "Run tos_legal_checker for top candidates.",
            "Record selected opportunities with ledger_skill before execution planning.",
        ]
        return OpportunityScoutResult(
            mission=request.mission,
            generated_at=utc_now().isoformat(timespec="seconds"),
            summary=summary,
            candidates_reviewed=len(request.source_documents),
            candidates_rejected=len(rejected),
            opportunities=ranked,
            rejected_candidates=rejected,
            top_recommendations=top_recommendations,
            search_summary=summary,
            source_coverage=source_coverage,
            next_actions=next_actions,
        )
