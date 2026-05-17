"""Deterministic scoring for opportunity candidates."""

from __future__ import annotations

from openclaw_moneybot.shared.types import ConfidenceLevel, RiskLevel


def _confidence_score(value: ConfidenceLevel) -> float:
    return {
        ConfidenceLevel.LOW: 1.0,
        ConfidenceLevel.MEDIUM: 2.0,
        ConfidenceLevel.HIGH: 3.0,
    }[value]


def _risk_penalty(value: RiskLevel) -> float:
    return {
        RiskLevel.LOW: 0.0,
        RiskLevel.MEDIUM: 2.0,
        RiskLevel.HIGH: 5.0,
        RiskLevel.CRITICAL: 10.0,
    }[value]


def score_candidate(
    *,
    estimated_revenue_high_usd: float,
    required_spend_usd: float,
    max_loss_usd: float,
    estimated_time_hours: float,
    skill_fit: ConfidenceLevel,
    legal_risk: RiskLevel,
    tos_risk: RiskLevel,
    operational_complexity: ConfidenceLevel,
    has_rules_url: bool,
    has_evidence: bool,
) -> dict[str, float]:
    """Compute a conservative opportunity score."""
    legitimacy_score = 3.0 if has_rules_url else 1.0
    fit_score = _confidence_score(skill_fit)
    roi_score = max(0.0, min(10.0, estimated_revenue_high_usd / 20.0))
    risk_score = 10.0 - _risk_penalty(legal_risk) - _risk_penalty(tos_risk)
    evidence_score = 2.0 if has_evidence else 0.0
    speed_penalty = min(4.0, estimated_time_hours / 6.0)
    spend_penalty = min(5.0, required_spend_usd / 5.0)
    loss_penalty = min(5.0, max_loss_usd / 5.0)
    complexity_penalty = _confidence_score(operational_complexity) - 1.0

    total = (
        legitimacy_score
        + fit_score
        + roi_score
        + risk_score
        + evidence_score
        - speed_penalty
        - spend_penalty
        - loss_penalty
        - complexity_penalty
    )
    return {
        "legitimacy_score": legitimacy_score,
        "fit_score": fit_score,
        "roi_score": roi_score,
        "risk_score": risk_score,
        "evidence_score": evidence_score,
        "total": total,
    }
