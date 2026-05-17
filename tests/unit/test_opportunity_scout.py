"""Tests for the opportunity scout."""

from __future__ import annotations

import json
from pathlib import Path

from openclaw_moneybot.skills.opportunity_scout import (
    OpportunityScout,
    OpportunityScoutRequest,
    ScoutSourceDocument,
)


def load_documents() -> list[ScoutSourceDocument]:
    payload = json.loads(
        Path("tests/fixtures/opportunity_scout/sources.json").read_text(encoding="utf-8")
    )
    return [ScoutSourceDocument.model_validate(item) for item in payload]


def make_request(**overrides: object) -> OpportunityScoutRequest:
    payload: dict[str, object] = {
        "mission": "Find low-budget developer opportunities.",
        "budget_usd": 100,
        "skills_available": ["python", "documentation", "web"],
        "blocked_categories": ["gambling"],
        "preferred_categories": ["bounty", "documentation", "micro_product"],
        "max_results": 10,
        "time_budget_hours": 8,
        "evidence_required": True,
        "source_documents": load_documents(),
    }
    payload.update(overrides)
    return OpportunityScoutRequest.model_validate(payload)


def test_safe_opportunity_extraction_from_fixture_sources() -> None:
    result = OpportunityScout().evaluate(make_request())

    assert result.opportunities
    assert result.opportunities[0].recommended_next_step in {"run_tos_check", "research_more"}


def test_prohibited_opportunity_rejection() -> None:
    result = OpportunityScout().evaluate(make_request())

    rejected_names = {candidate.name for candidate in result.rejected_candidates}
    assert "Token trading bot" in rejected_names


def test_duplicate_detection() -> None:
    result = OpportunityScout().evaluate(make_request())

    keys = [
        (candidate.name, str(candidate.source_url))
        for candidate in result.opportunities
    ]
    assert len(keys) == len(set(keys))


def test_scoring_order_prefers_low_risk_candidates() -> None:
    result = OpportunityScout().evaluate(make_request())

    assert result.opportunities[0].category in {"documentation", "bounty"}


def test_missing_rules_url_reduces_score() -> None:
    docs = load_documents()
    docs[0] = docs[0].model_copy(update={"rules_url": None})
    result = OpportunityScout().evaluate(make_request(source_documents=docs))

    docs_candidate = next(
        candidate for candidate in result.opportunities if candidate.name == "Docs bounty"
    )
    assert docs_candidate.tos_risk.value in {"medium", "low"}
    assert docs_candidate.recommended_next_step == "research_more"


def test_no_wallet_email_or_submit_calls_are_made() -> None:
    result = OpportunityScout().evaluate(make_request())

    assert all(
        candidate.recommended_next_step != "create_budget_plan"
        for candidate in result.opportunities
    )


def test_output_schema_validation() -> None:
    result = OpportunityScout().evaluate(make_request())

    assert result.top_recommendations
    assert result.candidates_reviewed == 5


def test_handoff_object_for_tos_checker() -> None:
    result = OpportunityScout().evaluate(make_request())

    first = result.opportunities[0]
    assert first.tos_handoff["opportunity_id"] == first.opportunity_id
    assert "proposed_action" in first.tos_handoff
