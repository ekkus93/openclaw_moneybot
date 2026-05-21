"""Unit tests for payout follow-up planning."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import (
    CounterpartyRiskTier,
    PayoutFollowupRecommendation,
    ReconciliationStatus,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.payout_followup_planner import (
    PayoutFollowupPlanner,
    PayoutFollowupPlanRequest,
)


def make_planner(tmp_path: Path) -> PayoutFollowupPlanner:
    return PayoutFollowupPlanner(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        LedgerService.from_db_path(tmp_path / "moneybot.sqlite3"),
    )


def make_request(**overrides: object) -> PayoutFollowupPlanRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "reconciliation_status": ReconciliationStatus.LATE,
        "has_supporting_evidence": True,
        "days_since_expected": 1,
    }
    payload.update(overrides)
    return PayoutFollowupPlanRequest.model_validate(payload)


def test_late_inside_grace_period_recommends_wait(tmp_path: Path) -> None:
    result = make_planner(tmp_path).plan(make_request())

    assert result.recommendation is PayoutFollowupRecommendation.WAIT


def test_missing_proof_recommends_gather_evidence(tmp_path: Path) -> None:
    result = make_planner(tmp_path).plan(make_request(has_supporting_evidence=False))

    assert result.recommendation is PayoutFollowupRecommendation.GATHER_MISSING_PROOF


def test_underpaid_with_clear_evidence_recommends_draft_followup(tmp_path: Path) -> None:
    result = make_planner(tmp_path).plan(
        make_request(
            reconciliation_status=ReconciliationStatus.UNDERPAID,
            days_since_expected=5,
        )
    )

    assert result.recommendation is PayoutFollowupRecommendation.DRAFT_FOLLOWUP


def test_high_risk_counterparty_recommends_human_review(tmp_path: Path) -> None:
    result = make_planner(tmp_path).plan(
        make_request(counterparty_risk_tier=CounterpartyRiskTier.HIGH)
    )

    assert result.recommendation is PayoutFollowupRecommendation.HUMAN_REVIEW
