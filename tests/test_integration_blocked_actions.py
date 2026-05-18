from __future__ import annotations

from skills.budget_and_roi_planner.models import BudgetPlanRequest
from skills.budget_and_roi_planner.runner import run_budget_plan
from skills.email_drafter.models import EmailDraftRequest
from skills.email_drafter.runner import run_email_draft
from skills.moneybot_policy_guard.models import PolicyCheckRequest
from skills.moneybot_policy_guard.runner import run_policy_check
from skills.wallet_governor_client.models import WalletGovernorClientRequest
from skills.wallet_governor_client.runner import run_wallet_governor_client


def test_blocked_actions_fail_closed() -> None:
    result = run_policy_check(
        PolicyCheckRequest(
            action_id="gambling-1",
            action_type="gambling",
            description="Test gambling action",
            category="gambling",
            amount_usd=100.0,
        )
    )
    assert result.decision == "block"


def test_no_skill_sends_money_directly() -> None:
    result = run_wallet_governor_client(
        WalletGovernorClientRequest(
            action="send",
            amount_usd=10.0,
        )
    )
    assert result.status == "rejected"


def test_no_skill_accesses_private_keys() -> None:
    result = run_wallet_governor_client(
        WalletGovernorClientRequest(
            action="get_private_key",
            amount_usd=0.0,
        )
    )
    assert result.status == "rejected"


def test_no_skill_approves_own_prohibited_action() -> None:
    result = run_policy_check(
        PolicyCheckRequest(
            action_id="gambling-1",
            action_type="gambling",
            description="Test gambling action",
            category="gambling",
            amount_usd=100.0,
        )
    )
    assert result.decision == "block"


def test_every_external_message_is_draft_only() -> None:
    result = run_email_draft(
        EmailDraftRequest(
            opportunity_id="test-1",
            opportunity_name="Test",
            recipient="test@example.com",
            subject="Test",
            body="Test",
            is_draft_only=True,
        )
    )
    assert result.is_sent is False


def test_budget_plan_negative_roi_rejected() -> None:
    result = run_budget_plan(
        BudgetPlanRequest(
            opportunity_id="test-1",
            opportunity_name="Test",
            tos_legal_check_id="tos-1",
            policy_decision_id="policy-1",
            proposed_action="test",
            required_spend_usd=100.0,
            estimated_revenue_usd=50.0,
            fees_usd=10.0,
            wallet_balance_usd=100.0,
        )
    )
    assert result.decision == "reject"
