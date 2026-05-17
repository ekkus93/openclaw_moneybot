"""Deterministic decision rules for experiment review."""

from __future__ import annotations

from openclaw_moneybot.shared.types import ReviewDecisionType
from openclaw_moneybot.skills.experiment_reviewer.metrics import ReviewMetrics

MAJOR_STOP_FLAGS = {"legal_red_flag", "tos_violation", "policy_violation"}
HUMAN_REVIEW_FLAGS = {"complaint", "payment_dispute", "privacy_issue"}


def decide_review(
    *,
    metrics: ReviewMetrics,
    incident_flags: list[str],
    success_metric_met: bool,
    stop_condition_triggered: bool,
) -> tuple[str, ReviewDecisionType, list[str], list[str], list[str], list[str]]:
    """Return status, decision, lessons, next actions, blocklist, and policy feedback."""
    flag_set = set(incident_flags)
    lessons: list[str] = []
    next_actions: list[str] = []
    new_blocklist_patterns: list[str] = []
    policy_feedback: list[str] = []
    if flag_set & MAJOR_STOP_FLAGS:
        lessons.append("A legal, terms, or policy red flag was detected during review.")
        next_actions.append("Stop the experiment and preserve the evidence trail for review.")
        new_blocklist_patterns.append(
            "Block experiments that reproduce the flagged compliance pattern."
        )
        policy_feedback.append("Escalate similar opportunities to a hard block.")
        return (
            "reviewed",
            ReviewDecisionType.STOP,
            lessons,
            next_actions,
            new_blocklist_patterns,
            policy_feedback,
        )
    if metrics.evidence_quality == "poor" and (metrics.spent_usd > 0 or metrics.revenue_usd > 0):
        lessons.append("Financial activity exists without enough review evidence.")
        next_actions.append(
            "Collect receipts, transaction records, and outcome evidence before continuing."
        )
        return (
            "insufficient_data",
            ReviewDecisionType.HUMAN_REVIEW,
            lessons,
            next_actions,
            new_blocklist_patterns,
            policy_feedback,
        )
    if flag_set & HUMAN_REVIEW_FLAGS:
        lessons.append("The outcome triggered a complaint, dispute, or privacy-sensitive issue.")
        next_actions.append("Escalate to human review before any follow-up action.")
        return (
            "reviewed",
            ReviewDecisionType.HUMAN_REVIEW,
            lessons,
            next_actions,
            new_blocklist_patterns,
            policy_feedback,
        )
    if stop_condition_triggered and not success_metric_met:
        lessons.append("The stop condition was reached without satisfying the success metric.")
        next_actions.append("Stop the experiment and prefer lower-risk alternatives.")
        return (
            "reviewed",
            ReviewDecisionType.STOP,
            lessons,
            next_actions,
            new_blocklist_patterns,
            policy_feedback,
        )
    if metrics.budget_exceeded:
        lessons.append("Actual spend exceeded the approved budget plan.")
        next_actions.append("Require human review before any further spend.")
        policy_feedback.append("Flag follow-up spend when actual cost exceeds the plan.")
        return (
            "reviewed",
            ReviewDecisionType.HUMAN_REVIEW,
            lessons,
            next_actions,
            new_blocklist_patterns,
            policy_feedback,
        )
    if metrics.net_usd > 0 or success_metric_met:
        lessons.append("The experiment produced positive or qualified signal.")
        next_actions.append(
            "Continue only with fresh policy and budget confirmation for any next step."
        )
        return (
            "reviewed",
            ReviewDecisionType.CONTINUE,
            lessons,
            next_actions,
            new_blocklist_patterns,
            policy_feedback,
        )
    if metrics.spent_usd <= 5:
        lessons.append("The experiment was inconclusive but remained low cost.")
        next_actions.append("Retry with a narrower scope and explicit evidence requirements.")
        return (
            "reviewed",
            ReviewDecisionType.RETRY_WITH_CHANGES,
            lessons,
            next_actions,
            new_blocklist_patterns,
            policy_feedback,
        )
    lessons.append("The outcome remains ambiguous and needs a human decision.")
    next_actions.append("Pause the experiment until a human reviews the current evidence.")
    return (
        "insufficient_data",
        ReviewDecisionType.HUMAN_REVIEW,
        lessons,
        next_actions,
        new_blocklist_patterns,
        policy_feedback,
    )
