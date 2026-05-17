"""Service entrypoint for the policy guard."""

from __future__ import annotations

from openclaw_moneybot.shared.config import MoneyBotPolicyConfig
from openclaw_moneybot.skills.moneybot_policy_guard.models import (
    PolicyCheckRequest,
    PolicyCheckResult,
)
from openclaw_moneybot.skills.moneybot_policy_guard.rules import evaluate_policy


class MoneyBotPolicyGuard:
    """Deterministic policy guard service."""

    def __init__(self, config: MoneyBotPolicyConfig) -> None:
        self.config = config

    def evaluate(self, request: PolicyCheckRequest) -> PolicyCheckResult:
        """Evaluate a proposed action against policy rules."""
        return evaluate_policy(request, self.config)
