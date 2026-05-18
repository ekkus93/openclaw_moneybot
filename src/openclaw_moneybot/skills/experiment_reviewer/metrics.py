"""Deterministic review metrics."""

from __future__ import annotations

from dataclasses import dataclass

from openclaw_moneybot.shared import BudgetPlan, EvidenceRecord, WalletTransactionRecord


@dataclass(frozen=True)
class ReviewMetrics:
    """Calculated experiment metrics."""

    spent_usd: float
    fee_usd: float
    revenue_usd: float
    net_usd: float
    roi_percent: float
    evidence_quality: str
    budget_exceeded: bool


def calculate_review_metrics(
    *,
    budget_plan: BudgetPlan,
    wallet_transactions: list[WalletTransactionRecord],
    revenue_usd: float,
    unrealized_value_usd: float,
    fees_usd: float,
    evidence_records: list[EvidenceRecord],
) -> ReviewMetrics:
    """Summarize financial and evidence metrics."""
    spent_usd = round(sum(item.total_usd_estimate for item in wallet_transactions), 2)
    fee_usd_total = round(sum(item.fee_usd_estimate for item in wallet_transactions), 2)
    net_usd = round(revenue_usd + unrealized_value_usd - spent_usd - fees_usd, 2)
    roi_percent = 0.0 if spent_usd <= 0 else round((net_usd / spent_usd) * 100, 2)
    budget_exceeded = spent_usd > budget_plan.recommended_budget_usd
    evidence_quality = "poor"
    if evidence_records:
        evidence_quality = "acceptable"
    if evidence_records and (spent_usd == 0 or wallet_transactions):
        evidence_quality = "good"
    return ReviewMetrics(
        spent_usd=spent_usd,
        fee_usd=fee_usd_total,
        revenue_usd=revenue_usd,
        net_usd=net_usd,
        roi_percent=roi_percent,
        evidence_quality=evidence_quality,
        budget_exceeded=budget_exceeded,
    )
