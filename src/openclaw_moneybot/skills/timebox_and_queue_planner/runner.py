"""Deterministic queue planning."""

from __future__ import annotations

from openclaw_moneybot.shared.types import QueuePriority, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.support import record_structured_result
from openclaw_moneybot.skills.timebox_and_queue_planner.models import (
    QueueOpportunityItem,
    QueuePlanRequest,
    QueuePlanResult,
)
from openclaw_moneybot.utils.ids import make_id


def _priority_for_item(
    item: QueueOpportunityItem,
    request: QueuePlanRequest,
) -> tuple[QueuePriority, str]:
    if item.review_blocked:
        return QueuePriority.DEFER, "review_blocked"
    if request.current_active_experiments >= request.max_concurrent_experiments:
        return QueuePriority.DEFER, "concurrency_cap_reached"
    if item.budget_reservation > request.available_budget_usd:
        return QueuePriority.DEFER, "budget_headroom_insufficient"
    if item.recent_failures >= 2:
        return QueuePriority.LOW, "repeated_failures"
    if (
        item.deadline_days is not None
        and item.deadline_days <= 1
        and item.expected_net_revenue_usd > 0
    ):
        return QueuePriority.CRITICAL, "near_deadline_positive_roi"
    if item.expected_net_revenue_usd > 0 and item.risk_score <= 25:
        return QueuePriority.HIGH, "positive_roi_low_risk"
    return QueuePriority.MEDIUM, "normal_priority"


class TimeboxAndQueuePlanner:
    """Prioritize bounded experiments without bypassing gates."""

    def __init__(self, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service

    def plan(self, request: QueuePlanRequest) -> QueuePlanResult:
        """Produce a deterministic queue plan."""
        queue_plan_id = make_id("queue_plan")
        planned_items: list[dict[str, str | float]] = []
        priority_order = {
            QueuePriority.CRITICAL: 0,
            QueuePriority.HIGH: 1,
            QueuePriority.MEDIUM: 2,
            QueuePriority.LOW: 3,
            QueuePriority.DEFER: 4,
        }
        for item in sorted(
            request.items,
            key=lambda candidate: (
                -candidate.expected_net_revenue_usd,
                candidate.deadline_days or 999,
            ),
        ):
            priority, reason = _priority_for_item(item, request)
            planned_items.append(
                {
                    "opportunity_id": item.opportunity_id,
                    "priority": priority.value,
                    "timebox_hours": item.timebox_hours,
                    "budget_reservation": item.budget_reservation,
                    "queue_reason": reason if priority is not QueuePriority.DEFER else "",
                    "defer_reason": reason if priority is QueuePriority.DEFER else "",
                }
            )
        planned_items.sort(
            key=lambda item: priority_order[QueuePriority(str(item["priority"]))]
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=queue_plan_id,
            record_type=RecordType.QUEUE_PLAN,
            related_record_id=request.plan_scope_id,
            payload={"items": planned_items},
        )
        return QueuePlanResult(
            queue_plan_id=queue_plan_id,
            items=planned_items,
            ledger_record=ledger_record,
        )
