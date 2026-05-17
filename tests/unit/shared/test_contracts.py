"""Tests for shared contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from openclaw_moneybot.shared.contracts import MoneyBotAction, Opportunity, PolicyDecision
from openclaw_moneybot.shared.types import ActionType, PolicyDecisionType, RiskLevel


def test_contract_round_trip_serialization() -> None:
    """Representative contract models round-trip cleanly."""
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    opportunity = Opportunity(
        created_at=created_at,
        opportunity_id="opp_123",
        name="Small OSS bounty",
        category="bounty",
        status="discovered",
        source_url="https://example.com/bounty",
        rules_url="https://example.com/rules",
        required_spend_usd=0,
        estimated_revenue_usd=50,
        max_loss_usd=0,
        raw_json={"source": "fixture"},
    )

    restored = Opportunity.model_validate_json(opportunity.model_dump_json())

    assert restored == opportunity


def test_policy_decision_requires_timezone_aware_expiry() -> None:
    """Naive datetimes are rejected."""
    with pytest.raises(ValidationError):
        PolicyDecision(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            policy_decision_id="policy_123",
            decision=PolicyDecisionType.ALLOW,
            risk_level=RiskLevel.LOW,
            policy_version="v1",
            request_fingerprint="abc123",
            expires_at=datetime(2026, 1, 2),
        )


def test_action_contract_rejects_negative_amount() -> None:
    """Action amounts must be non-negative."""
    with pytest.raises(ValidationError):
        MoneyBotAction(
            action_id="action_123",
            action_type=ActionType.SPEND,
            title="Buy domain",
            description="Purchase the domain for the experiment",
            category="infrastructure",
            source_urls=["https://example.com"],
            amount_usd=-1,
        )
