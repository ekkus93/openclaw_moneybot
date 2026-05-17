"""Risk classification for budget planning."""

from __future__ import annotations

from openclaw_moneybot.shared.types import RiskLevel


def classify_budget_risk(
    *,
    recommended_budget_usd: float,
    max_single_spend_usd: float,
    wallet_balance_usd: float,
    recurring_costs_usd: float,
    unknown_fees: bool,
) -> RiskLevel:
    """Classify the budget plan's risk."""
    if unknown_fees or recurring_costs_usd > 0:
        return RiskLevel.MEDIUM
    if recommended_budget_usd > max_single_spend_usd or recommended_budget_usd > wallet_balance_usd:
        return RiskLevel.HIGH
    return RiskLevel.LOW
