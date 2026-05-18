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
        fees_usd = (request.fees_usd or 0) + (request.platform_fees_usd or 0) + (
            request.wallet_fee_usd or 0
        )
        recurring_costs_usd = request.recurring_costs_usd or 0
        unknown_fees = request.fees_usd is None
        estimated_revenue_usd = request.estimated_revenue_usd or 0
        total_budget = recommended_budget(
            request.required_spend_usd, fees_usd, recurring_costs_usd
        )
        expected_net = expected_net_revenue(
            estimated_revenue_usd,
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
            reasons.append("Policy approval must be exactly allow.")
        if request.tos_legal_check_id is None or request.tos_legal_decision != "proceed":
            decision = BudgetDecisionType.REJECT
            reasons.append("TOS/legal approval must be exactly proceed.")
        if total_budget > self.config.max_single_spend_usd:
            decision = BudgetDecisionType.REJECT
            reasons.append("The plan exceeds the configured max single spend.")
        if total_budget > request.max_loss_usd:
            decision = BudgetDecisionType.REJECT
            reasons.append("Worst-case loss exceeds the explicit max_loss_usd.")
        if total_budget > request.wallet_balance_usd:
            decision = BudgetDecisionType.REJECT
            reasons.append("The wallet balance cannot support the proposed plan.")
        if total_budget > request.daily_spend_remaining_usd:
            decision = BudgetDecisionType.REJECT
            reasons.append("The plan exceeds the remaining daily spend limit.")
        if recurring_costs_usd > 0 and (
            request.recurring_cost_cap_usd is None
            or recurring_costs_usd > request.recurring_cost_cap_usd
        ):
            decision = BudgetDecisionType.REJECT
            reasons.append("Recurring billing is uncapped.")
        if unknown_fees:
            decision = BudgetDecisionType.HUMAN_REVIEW
            reasons.append("Unknown fees require review before execution.")
        if request.expected_revenue_unknown:
            decision = BudgetDecisionType.SIMULATE
            reasons.append("Revenue is too uncertain for execution.")
        if expected_net < 0 and not request.expected_revenue_unknown:
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
            max_loss_usd=request.max_loss_usd,
            expected_gross_revenue_usd=estimated_revenue_usd,
            expected_net_revenue_usd=expected_net,
            break_even_condition=break_even_condition(total_budget, estimated_revenue_usd),
            success_metric=request.success_metric,
            stop_condition=request.stop_condition,
            required_records=["budget_snapshot", "terms_snapshot"],
            required_evidence_ids=request.evidence_archive_ids,
            risk_level=risk_level,
            wallet_spend_request_allowed=decision is BudgetDecisionType.EXECUTE_REQUEST,
            approved_spend_categories=request.approved_spend_categories,
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
                "max_wallet_spend_amount": total_budget,
                "asset": request.asset,
                "wallet_spend_allowed": True,
                "approved_spend_categories": request.approved_spend_categories,
                "policy_decision_id": plan.policy_decision_id,
                "tos_legal_check_id": plan.tos_legal_check_id,
                "required_evidence_ids": request.evidence_archive_ids,
                "stop_condition": request.stop_condition,
                "required_records": plan.required_records,
            }
        return BudgetPlanResult(budget_plan=plan, wallet_handoff=wallet_handoff)
