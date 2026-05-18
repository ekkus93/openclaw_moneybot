from __future__ import annotations

from skills.budget_and_roi_planner.models import (
    BudgetPlanRequest,
    BudgetPlanResult,
)


def analyze(req: BudgetPlanRequest) -> BudgetPlanResult:
    total_cost = req.required_spend_usd + req.fees_usd
    if req.recurring_costs_usd is not None:
        total_cost += req.recurring_costs_usd

    net = req.estimated_revenue_usd - total_cost
    risk = _compute_risk(req, net)

    if not _has_enough_funds(req, total_cost):
        return _reject_insufficient_funds(
            req,
            total_cost,
            risk,
        )

    if not _has_enough_daily_spend(req, total_cost):
        return _reject_daily_limit_exceeded(
            req,
            total_cost,
            risk,
        )

    if net < 0:
        return _reject_negative_roi(req, total_cost, risk)

    return _create_plan(
        req,
        total_cost,
        net,
        risk,
    )


def _reject_insufficient_funds(
    req: BudgetPlanRequest,
    total_cost: float,
    risk: str,
) -> BudgetPlanResult:
    return BudgetPlanResult(
        budget_plan_id=f"{req.opportunity_id}-budget-insufficient",
        decision="reject",
        recommended_budget_usd=total_cost,
        max_loss_usd=total_cost,
        expected_gross_revenue_usd=req.estimated_revenue_usd,
        expected_net_revenue_usd=req.estimated_revenue_usd - total_cost,
        break_even_condition=None,
        success_metric="none",
        stop_condition="insufficient_funds",
        required_records=["budget_reject_insufficient"],
        risk_level=risk,
        wallet_spend_request_allowed=False,
        reasons=["Insufficient wallet balance"],
    )


def _reject_daily_limit_exceeded(
    req: BudgetPlanRequest,
    total_cost: float,
    risk: str,
) -> BudgetPlanResult:
    return BudgetPlanResult(
        budget_plan_id=f"{req.opportunity_id}-budget-daily-limit",
        decision="reject",
        recommended_budget_usd=total_cost,
        max_loss_usd=total_cost,
        expected_gross_revenue_usd=req.estimated_revenue_usd,
        expected_net_revenue_usd=req.estimated_revenue_usd - total_cost,
        break_even_condition=None,
        success_metric="none",
        stop_condition="daily_limit_exceeded",
        required_records=["budget_reject_daily_limit"],
        risk_level=risk,
        wallet_spend_request_allowed=False,
        reasons=["Daily spend limit exceeded"],
    )


def _reject_negative_roi(
    req: BudgetPlanRequest,
    total_cost: float,
    risk: str,
) -> BudgetPlanResult:
    return BudgetPlanResult(
        budget_plan_id=f"{req.opportunity_id}-budget-negative-roi",
        decision="reject",
        recommended_budget_usd=total_cost,
        max_loss_usd=total_cost,
        expected_gross_revenue_usd=req.estimated_revenue_usd,
        expected_net_revenue_usd=req.estimated_revenue_usd - total_cost,
        break_even_condition=None,
        success_metric="none",
        stop_condition="negative_roi",
        required_records=["budget_reject_negative_roi"],
        risk_level=risk,
        wallet_spend_request_allowed=False,
        reasons=["Negative ROI"],
    )


def _create_plan(
    req: BudgetPlanRequest,
    total_cost: float,
    net: float,
    risk: str,
) -> BudgetPlanResult:
    if risk == "high":
        decision = "human_review"
        wallet_spend_allowed = False
    else:
        decision = "execute_request"
        wallet_spend_allowed = True

    return BudgetPlanResult(
        budget_plan_id=f"{req.opportunity_id}-budget-plan",
        decision=decision,
        recommended_budget_usd=total_cost,
        max_loss_usd=total_cost,
        expected_gross_revenue_usd=req.estimated_revenue_usd,
        expected_net_revenue_usd=net,
        break_even_condition=None,
        success_metric="positive_net_revenue",
        stop_condition="max_loss_reached",
        required_records=["budget_plan_created"],
        risk_level=risk,
        wallet_spend_request_allowed=wallet_spend_allowed,
        reasons=["Positive ROI", "Funds available"],
    )


def _compute_risk(req: BudgetPlanRequest, net: float) -> str:
    ratio = (
        req.required_spend_usd / req.estimated_revenue_usd
        if req.estimated_revenue_usd > 0
        else float("inf")
    )
    if ratio > 0.8:
        return "high"
    if ratio > 0.5:
        return "medium"
    return "low"


def _has_enough_funds(req: BudgetPlanRequest, total_cost: float) -> bool:
    return req.wallet_balance_usd >= total_cost


def _has_enough_daily_spend(
    req: BudgetPlanRequest,
    total_cost: float,
) -> bool:
    if req.daily_spend_remaining_usd is None:
        return True
    return req.daily_spend_remaining_usd >= total_cost
