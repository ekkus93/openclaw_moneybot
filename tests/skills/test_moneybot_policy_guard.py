from __future__ import annotations

from skills.moneybot_policy_guard.models import PolicyCheckRequest
from skills.moneybot_policy_guard.runner import run_policy_check


def test_allow_internal() -> None:
    req = PolicyCheckRequest(
        action_id="test-1",
        action_type="internal",
        description="Internal research",
        category="research",
    )
    decision = run_policy_check(req)
    assert decision.decision == "allow"


def test_block_gambling() -> None:
    req = PolicyCheckRequest(
        action_id="test-2",
        action_type="spend",
        description="Place bet",
        category="gambling",
        amount_usd=10.0,
    )
    decision = run_policy_check(req)
    assert decision.decision == "block"


def test_block_missing_amount() -> None:
    req = PolicyCheckRequest(
        action_id="test-3",
        action_type="spend",
        description="Pay vendor",
        category="payment",
    )
    decision = run_policy_check(req)
    assert decision.decision == "block"


def test_needs_review_unknown_category() -> None:
    req = PolicyCheckRequest(
        action_id="test-4",
        action_type="internal",
        description="Test",
        category="unknown",
    )
    decision = run_policy_check(req)
    assert decision.decision == "allow"
