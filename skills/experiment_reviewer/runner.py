from __future__ import annotations

from skills.experiment_reviewer.models import (
    ExperimentReviewRequest,
    ExperimentReviewResult,
)


def run_experiment_review(request: ExperimentReviewRequest) -> ExperimentReviewResult:
    net_profit = request.actual_revenue_usd - request.actual_spend_usd
    roi_percent = (
        (net_profit / request.actual_spend_usd * 100)
        if request.actual_spend_usd > 0
        else 0.0
    )

    if net_profit < 0:
        decision = "fail_experiment"
        risk_level = "high"
    elif net_profit > 0:
        decision = "success"
        risk_level = "low"
    else:
        decision = "neutral"
        risk_level = "medium"

    return ExperimentReviewResult(
        experiment_id=request.experiment_id,
        decision=decision,
        risk_level=risk_level,
        net_profit_usd=net_profit,
        roi_percent=roi_percent,
        required_records=["experiment_review"],
        reasons=["Experiment review complete"],
    )
