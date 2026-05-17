from __future__ import annotations

from skills.moneybot_policy_guard.models import PolicyCheckRequest, PolicyDecision
from skills.moneybot_policy_guard.rules import evaluate


def run_policy_check(request: PolicyCheckRequest) -> PolicyDecision:
    decision = evaluate(request)
    return decision
