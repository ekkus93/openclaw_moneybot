"""Unit tests for strategy memory summaries."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import (
    CounterpartyRiskTier,
    ReconciliationStatus,
    StrategyLessonCategory,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.strategy_memory_summarizer import (
    StrategyMemorySummarizer,
    StrategyMemorySummaryRequest,
)


def make_summarizer(tmp_path: Path) -> StrategyMemorySummarizer:
    return StrategyMemorySummarizer(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        LedgerService.from_db_path(tmp_path / "moneybot.sqlite3"),
    )


def make_request(**overrides: object) -> StrategyMemorySummaryRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "experiment_review_id": "review_001",
        "scope": "opportunity",
        "net_usd": 10.0,
        "roi_percent": 50.0,
        "time_spent_hours": 2.0,
        "reconciliation_status": ReconciliationStatus.MATCHED,
        "counterparty_risk_tier": CounterpartyRiskTier.LOW,
    }
    payload.update(overrides)
    return StrategyMemorySummaryRequest.model_validate(payload)


def test_successful_pattern_becomes_reusable_heuristic(tmp_path: Path) -> None:
    result = make_summarizer(tmp_path).summarize(make_request())

    assert "Prefer opportunities with positive realized ROI." in result.heuristics_to_keep


def test_one_off_noisy_incident_does_not_become_hard_rule(tmp_path: Path) -> None:
    result = make_summarizer(tmp_path).summarize(
        make_request(net_usd=-1.0, roi_percent=-5.0)
    )

    assert StrategyLessonCategory.RISK in result.lesson_categories


def test_contradictory_results_become_tentative(tmp_path: Path) -> None:
    result = make_summarizer(tmp_path).summarize(
        make_request(contradictory_results=True)
    )

    assert result.tentative_hypotheses
