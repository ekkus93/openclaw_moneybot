from __future__ import annotations

from shared.contracts import (
    ActionCategory,
    BlockedCategory,
    BudgetPlan,
    DecisionState,
    EvidenceRecord,
    ExperimentReview,
    MoneyBotAction,
    Opportunity,
    PolicyDecision,
    RiskLevel,
    SpendRequest,
)
from shared.error import MoneyBotError


def test_moneybot_action_minimal() -> None:
    action = MoneyBotAction(
        action_id="test-1",
        action_type=ActionCategory.internal,
        description="Internal test",
        category="research",
    )
    assert action.action_id == "test-1"


def test_policy_decision_allow() -> None:
    decision = PolicyDecision(
        decision=DecisionState.allow,
        risk_level=RiskLevel.low,
        blocked_reasons=[],
        required_mitigations=[],
        matched_rules=["ALLOW_INTERNAL"],
        safe_next_steps=["continue"],
    )
    assert decision.decision == DecisionState.allow


def test_opportunity_basic() -> None:
    opp = Opportunity(
        opportunity_id="opp-1",
        name="Test bounty",
        category="bounty",
        source_url="https://example.com",
    )
    assert opp.opportunity_id == "opp-1"


def test_budget_plan_minimal() -> None:
    plan = BudgetPlan(
        budget_plan_id="bp-1",
        opportunity_id="opp-1",
        tos_legal_check_id="tlc-1",
        policy_decision_id="pd-1",
        proposed_action="submit bounty",
        required_spend_usd=10.0,
        estimated_revenue_usd=50.0,
        fees_usd=1.0,
        recurring_costs_usd=0.0,
        wallet_balance_usd=100.0,
        daily_spend_remaining_usd=25.0,
    )
    assert plan.required_spend_usd == 10.0


def test_spend_request_minimal() -> None:
    req = SpendRequest(
        spend_request_id="sr-1",
        budget_plan_id="bp-1",
        policy_decision_id="pd-1",
        ledger_event_id="le-1",
        amount_usd=5.0,
        asset="BTC",
        destination="bc1qtest",
        counterparty="vendor",
        purpose="invoice",
        category="payment",
    )
    assert req.amount_usd == 5.0


def test_evidence_record() -> None:
    rec = EvidenceRecord(
        evidence_id="ev-1",
        related_type="opportunity",
        related_id="opp-1",
        evidence_type="source_page",
        source_url="https://example.com",
    )
    assert rec.evidence_id == "ev-1"


def test_experiment_review() -> None:
    review = ExperimentReview(
        experiment_review_id="er-1",
        opportunity_id="opp-1",
        spent_usd=10.0,
        revenue_usd=20.0,
        net_usd=10.0,
        roi_percent=100.0,
        success_metric_status="met",
        stop_condition_status="not_reached",
        lessons=["good"],
        decision="continue",
        recommended_next_actions=["scale"],
        new_blocklist_patterns=[],
    )
    assert review.net_usd == 10.0


def test_moneybot_error_not_found() -> None:
    err = MoneyBotError.not_found("resource-1")
    assert err.error_code == "NOT_FOUND"
    assert err.recoverable is True


def test_moneybot_error_invalid_request() -> None:
    err = MoneyBotError.invalid_request("missing field X")
    assert err.error_code == "INVALID_REQUEST"
    assert err.details["detail"] == "missing field X"


def test_moneybot_error_blocked() -> None:
    err = MoneyBotError.blocked("gambling")
    assert err.error_code == "BLOCKED"
    assert err.recoverable is False


def test_enums() -> None:
    assert RiskLevel.low == "low"
    assert DecisionState.allow == "allow"
    assert ActionCategory.spend == "spend"
    assert BlockedCategory.gambling == "gambling"
