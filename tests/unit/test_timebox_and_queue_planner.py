"""Unit tests for queue planning."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared.types import QueuePriority
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.timebox_and_queue_planner import (
    QueueOpportunityItem,
    QueuePlanRequest,
    TimeboxAndQueuePlanner,
)


def make_planner(tmp_path: Path) -> TimeboxAndQueuePlanner:
    return TimeboxAndQueuePlanner(LedgerService.from_db_path(tmp_path / "moneybot.sqlite3"))


def make_request(items: list[QueueOpportunityItem], **overrides: object) -> QueuePlanRequest:
    payload: dict[str, object] = {
        "plan_scope_id": "queue_scope_001",
        "items": items,
        "available_budget_usd": 20.0,
        "max_concurrent_experiments": 2,
        "current_active_experiments": 0,
    }
    payload.update(overrides)
    return QueuePlanRequest.model_validate(payload)


def test_high_roi_near_deadline_ranks_first(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)
    result = planner.plan(
        make_request(
            [
                QueueOpportunityItem(
                    opportunity_id="opp_fast",
                    expected_net_revenue_usd=10,
                    timebox_hours=1,
                    deadline_days=1,
                ),
                QueueOpportunityItem(
                    opportunity_id="opp_slow",
                    expected_net_revenue_usd=8,
                    timebox_hours=2,
                    deadline_days=5,
                ),
            ]
        )
    )

    assert result.items[0]["priority"] == QueuePriority.CRITICAL.value


def test_review_blocked_item_is_deferred(tmp_path: Path) -> None:
    result = make_planner(tmp_path).plan(
        make_request(
            [
                QueueOpportunityItem(
                    opportunity_id="opp_blocked",
                    expected_net_revenue_usd=20,
                    timebox_hours=1,
                    review_blocked=True,
                )
            ]
        )
    )

    assert result.items[0]["priority"] == QueuePriority.DEFER.value


def test_budget_constrained_item_is_deferred_safely(tmp_path: Path) -> None:
    result = make_planner(tmp_path).plan(
        make_request(
            [
                QueueOpportunityItem(
                    opportunity_id="opp_costly",
                    expected_net_revenue_usd=20,
                    timebox_hours=1,
                    budget_reservation=100,
                )
            ],
            available_budget_usd=5,
        )
    )

    assert result.items[0]["defer_reason"] == "budget_headroom_insufficient"


def test_repeated_loser_gets_deprioritized(tmp_path: Path) -> None:
    result = make_planner(tmp_path).plan(
        make_request(
            [
                QueueOpportunityItem(
                    opportunity_id="opp_repeat",
                    expected_net_revenue_usd=20,
                    timebox_hours=1,
                    recent_failures=3,
                )
            ]
        )
    )

    assert result.items[0]["priority"] == QueuePriority.LOW.value
