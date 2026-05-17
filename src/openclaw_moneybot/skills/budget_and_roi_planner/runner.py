"""Service entrypoint for budget planning."""

from __future__ import annotations

from openclaw_moneybot.shared.config import MoneyBotPolicyConfig
from openclaw_moneybot.shared.contracts import BudgetPlan
from openclaw_moneybot.shared.types import BudgetDecisionType
from openclaw_moneybot.skills.budget_and_roi_planner.calculator import (
    break_even_condition,
    expected_net_revenue,
    recommended_budget,
)
from openclaw_moneybot.skills.budget_and_roi_planner.models import (
    BudgetPlanRequest,
    BudgetPlanResult,
)
from openclaw_moneybot.skills.budget_and_roi_planner.risk import classify_budget_risk
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class BudgetAndRoiPlanner:
    """Deterministic bounded experiment planner."""

    def __init__(self, config: MoneyBotPolicyConfig, ledger_service: LedgerService) -> None:
        self.config = config
        self.ledger_service = ledger_service

    def evaluate(self, request: BudgetPlanRequest) -> BudgetPlanResult:
        """Produce a bounded experiment plan and persist it."""
        reasons: list[str] = []
        decision = BudgetDecisionType.EXECUTE_REQUEST
        fees_usd = request.fees_usd or 0
        recurring_costs_usd = request.recurring_costs_usd or 0
        unknown_fees = request.fees_usd is None
        total_budget = recommended_budget(
            request.required_spend_usd, fees_usd, recurring_costs_usd
        )
        expected_net = expected_net_revenue(
            request.estimated_revenue_usd,
            request.required_spend_usd,
            fees_usd,
            recurring_costs_usd,
        )
        risk_level = classify_budget_risk(
            recommended_budget_usd=total_budget,
            max_single_spend_usd=self.config.max_single_spend_usd,
            wallet_balance_usd=request.wallet_balance_usd,
            recurring_costs_usd=recurring_costs_usd,
            unknown_fees=unknown_fees,
        )

        if request.policy_decision_id is None or request.policy_decision != "allow":
            decision = BudgetDecisionType.REJECT
            reasons.append("A non-blocked policy decision is required.")
        if request.tos_legal_check_id is None or request.tos_legal_decision != "proceed":
            decision = BudgetDecisionType.REJECT
            reasons.append("A non-rejected TOS/legal check is required.")
        if total_budget > self.config.max_single_spend_usd:
            decision = BudgetDecisionType.REJECT
            reasons.append("The plan exceeds the configured max single spend.")
        if total_budget > request.wallet_balance_usd:
            decision = BudgetDecisionType.REJECT
            reasons.append("The wallet balance cannot support the proposed plan.")
        if total_budget > request.daily_spend_remaining_usd:
            decision = BudgetDecisionType.REJECT
            reasons.append("The plan exceeds the remaining daily spend limit.")
        if recurring_costs_usd > 0:
            decision = BudgetDecisionType.HUMAN_REVIEW
            reasons.append("Recurring billing requires human review.")
        if unknown_fees:
            decision = BudgetDecisionType.HUMAN_REVIEW
            reasons.append("Unknown fees require review before execution.")
        if expected_net < 0:
            decision = BudgetDecisionType.REJECT
            reasons.append("Expected net revenue is negative.")

        plan = BudgetPlan(
            created_at=utc_now(),
            budget_plan_id=make_id("budget"),
            opportunity_id=request.opportunity_id,
            policy_decision_id=request.policy_decision_id or "missing_policy",
            tos_legal_check_id=request.tos_legal_check_id or "missing_tos",
            decision=decision,
            recommended_budget_usd=total_budget,
            max_loss_usd=total_budget,
            expected_gross_revenue_usd=request.estimated_revenue_usd,
            expected_net_revenue_usd=expected_net,
            break_even_condition=break_even_condition(total_budget, request.estimated_revenue_usd),
            success_metric=request.success_metric,
            stop_condition=request.stop_condition,
            required_records=["budget_snapshot", "terms_snapshot"],
            risk_level=risk_level,
            wallet_spend_request_allowed=decision is BudgetDecisionType.EXECUTE_REQUEST,
            reasons=reasons,
        )
        if request.policy_decision_id is not None and request.tos_legal_check_id is not None:
            self.ledger_service.record_budget_plan(
                plan, idempotency_key=f"budget:{plan.budget_plan_id}"
            )

        wallet_handoff: dict[str, object] | None = None
        if decision is BudgetDecisionType.EXECUTE_REQUEST:
            wallet_handoff = {
                "budget_plan_id": plan.budget_plan_id,
                "opportunity_id": request.opportunity_id,
                "amount_usd": total_budget,
                "asset": request.asset,
                "required_records": plan.required_records,
            }
        return BudgetPlanResult(budget_plan=plan, wallet_handoff=wallet_handoff)
