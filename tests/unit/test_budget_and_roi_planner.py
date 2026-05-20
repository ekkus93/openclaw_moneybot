"""Tests for the budget and ROI planner."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from openclaw_moneybot.shared import Opportunity, PolicyDecision, TosLegalCheck
from openclaw_moneybot.shared.config import MoneyBotPolicyConfig
from openclaw_moneybot.shared.types import (
    ConfidenceLevel,
    PolicyDecisionType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.budget_and_roi_planner import (
    BudgetAndRoiPlanner,
    BudgetPlanRequest,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_planner(tmp_path: Path) -> BudgetAndRoiPlanner:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Budget test",
            category="bounty",
            status="discovered",
            source_url="https://example.com/opportunity",
            rules_url="https://example.com/rules",
            required_spend_usd=0,
            estimated_revenue_usd=25,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key="opportunity:opp_001",
    )
    ledger_service.record_policy_decision(
        PolicyDecision(
            created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            policy_decision_id="policy_001",
            opportunity_id="opp_001",
            decision=PolicyDecisionType.ALLOW,
            risk_level=RiskLevel.LOW,
            confidence=ConfidenceLevel.HIGH,
            policy_version="v1",
            request_fingerprint="fingerprint",
        ),
        idempotency_key="policy:policy_001",
    )
    ledger_service.record_tos_legal_check(
        TosLegalCheck(
            created_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
            tos_legal_check_id="tos_001",
            opportunity_id="opp_001",
            decision=TosDecisionType.PROCEED,
            confidence=ConfidenceLevel.HIGH,
            platform_terms_summary="Terms permit participation.",
            legal_risk_summary="No obvious legal risk.",
            tos_risk_summary="Low TOS risk.",
            evidence_archive_ids=["artifact_001"],
        ),
        idempotency_key="tos:tos_001",
    )
    config = MoneyBotPolicyConfig(
        policy_version="v1",
        blocked_categories=["gambling"],
        review_required_categories=["affiliate_marketing"],
        max_single_spend_usd=10,
        max_daily_spend_usd=20,
        max_weekly_spend_usd=40,
    )
    return BudgetAndRoiPlanner(config, ledger_service)


def make_request(**overrides: object) -> BudgetPlanRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "opportunity_name": "Budget test",
        "tos_legal_check_id": "tos_001",
        "tos_legal_decision": "proceed",
        "policy_decision_id": "policy_001",
        "policy_decision": "allow",
        "proposed_action": "Submit to the bounty.",
        "required_spend_usd": 5,
        "max_loss_usd": 8,
        "estimated_revenue_usd": 25,
        "estimated_time_hours": 2,
        "fees_usd": 1,
        "recurring_costs_usd": 0,
        "recurring_cost_cap_usd": 0,
        "asset": "BTC",
        "wallet_balance_usd": 100,
        "daily_spend_remaining_usd": 20,
        "evidence_archive_ids": ["artifact_001"],
        "approved_spend_categories": ["purchase"],
        "success_metric": "Accepted submission",
        "stop_condition": "Stop after rejection",
        "timebox_hours": 24,
    }
    payload.update(overrides)
    return BudgetPlanRequest.model_validate(payload)


def test_successful_low_cost_plan(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(make_request())

    assert result.budget_plan.decision.value == "execute_request"
    assert result.wallet_handoff is not None


def test_missing_policy_decision_rejects(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(make_request(policy_decision_id=None, policy_decision=None))

    assert result.budget_plan.decision.value == "reject"


def test_missing_tos_check_rejects(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(make_request(tos_legal_check_id=None, tos_legal_decision=None))

    assert result.budget_plan.decision.value == "reject"


def test_spend_over_max_single_limit_rejects(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(make_request(required_spend_usd=20, fees_usd=0))

    assert result.budget_plan.decision.value == "reject"


def test_recurring_billing_requires_review(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(make_request(recurring_costs_usd=2, recurring_cost_cap_usd=None))

    assert result.budget_plan.decision.value == "reject"


def test_unknown_fees_require_review(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(make_request(fees_usd=None))

    assert result.budget_plan.decision.value == "human_review"


def test_negative_expected_net_rejects(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(make_request(estimated_revenue_usd=1, fees_usd=2))

    assert result.budget_plan.decision.value == "reject"


def test_explicit_stop_condition_required() -> None:
    try:
        make_request(stop_condition="")
    except ValidationError as error:
        assert "stop_condition" in str(error)
    else:
        raise AssertionError("Expected stop_condition validation failure")


def test_wallet_handoff_object_shape(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(make_request())

    assert result.wallet_handoff is not None
    assert result.wallet_handoff["budget_plan_id"] == result.budget_plan.budget_plan_id
    assert result.wallet_handoff["approved_spend_categories"] == ["purchase"]


def test_uncertain_revenue_returns_simulate(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(
        make_request(
            estimated_revenue_usd=None,
            expected_revenue_unknown=True,
        )
    )

    assert result.budget_plan.decision.value == "simulate"


def test_policy_block_beats_revenue_uncertainty(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(
        make_request(
            policy_decision="block",
            expected_revenue_unknown=True,
            estimated_revenue_usd=None,
        )
    )

    assert result.budget_plan.decision.value == "reject"


def test_missing_reference_ids_do_not_insert_budget_plan(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(
        make_request(
            policy_decision_id="policy_missing",
            tos_legal_check_id="tos_missing",
        )
    )

    assert result.budget_plan.decision.value == "reject"
    assert planner.ledger_service.get_budget_plan(result.budget_plan.budget_plan_id) is None
    assert any("policy_missing" in reason for reason in result.budget_plan.reasons)
    assert any("tos_missing" in reason for reason in result.budget_plan.reasons)


def test_missing_opportunity_does_not_insert_budget_plan(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(make_request(opportunity_id="opp_missing"))

    assert result.budget_plan.decision.value == "reject"
    assert planner.ledger_service.get_budget_plan(result.budget_plan.budget_plan_id) is None
    assert any("opportunity_missing" in reason for reason in result.budget_plan.reasons)


def test_review_required_category_beats_simulate(tmp_path: Path) -> None:
    planner = make_planner(tmp_path)

    result = planner.evaluate(
        make_request(
            approved_spend_categories=["affiliate_marketing"],
            expected_revenue_unknown=True,
            estimated_revenue_usd=None,
        )
    )

    assert result.budget_plan.decision.value == "human_review"
