"""Deterministic budget math helpers."""

from __future__ import annotations


def expected_net_revenue(
    estimated_revenue_usd: float,
    required_spend_usd: float,
    fees_usd: float,
    recurring_costs_usd: float,
) -> float:
    """Calculate expected net revenue."""
    return estimated_revenue_usd - required_spend_usd - fees_usd - recurring_costs_usd


def recommended_budget(
    required_spend_usd: float, fees_usd: float, recurring_costs_usd: float
) -> float:
    """Calculate the total recommended budget."""
    return required_spend_usd + fees_usd + recurring_costs_usd


def break_even_condition(recommended_budget_usd: float, estimated_revenue_usd: float) -> str:
    """Build a simple break-even summary."""
    if estimated_revenue_usd <= 0:
        return "No viable break-even case because expected revenue is non-positive."
    return (
        f"Break even once realized revenue reaches ${recommended_budget_usd:.2f} "
        f"against an expected revenue of ${estimated_revenue_usd:.2f}."
    )
