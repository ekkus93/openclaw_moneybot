"""Tests for the narrow ledger API."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.plugins.ledger_api import LedgerApi, LedgerApiAuditEventRequest
from openclaw_moneybot.shared import BudgetPlan, Opportunity, PolicyDecision, TosLegalCheck
from openclaw_moneybot.shared.types import (
    BudgetDecisionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RecordType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_api(tmp_path: Path) -> LedgerApi:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Ledger API test",
            category="bounty",
            status="approved",
            source_url="https://example.com/opportunity",
            rules_url="https://example.com/rules",
            required_spend_usd=0,
            estimated_revenue_usd=25,
            max_loss_usd=5,
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
            platform_terms_summary="Proceed.",
            legal_risk_summary="Low.",
            tos_risk_summary="Low.",
            evidence_archive_ids=["artifact_001"],
        ),
        idempotency_key="tos:tos_001",
    )
    ledger_service.record_budget_plan(
        BudgetPlan(
            created_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
            budget_plan_id="budget_001",
            opportunity_id="opp_001",
            policy_decision_id="policy_001",
            tos_legal_check_id="tos_001",
            decision=BudgetDecisionType.EXECUTE_REQUEST,
            recommended_budget_usd=5,
            max_loss_usd=5,
            expected_gross_revenue_usd=20,
            expected_net_revenue_usd=15,
            break_even_condition="One payout",
            success_metric="Paid",
            stop_condition="Stop after one try",
            required_records=["budget_snapshot"],
            risk_level=RiskLevel.LOW,
            wallet_spend_request_allowed=True,
            reasons=["Within limits."],
        ),
        idempotency_key="budget:budget_001",
    )
    return LedgerApi(ledger_service)


def test_bundle_loads_typed_records(tmp_path: Path) -> None:
    bundle = make_api(tmp_path).get_opportunity_bundle("opp_001")

    assert bundle.opportunity.opportunity_id == "opp_001"
    assert bundle.policy_decisions
    assert bundle.tos_legal_checks
    assert bundle.budget_plans


def test_audit_event_is_written_idempotently(tmp_path: Path) -> None:
    api = make_api(tmp_path)

    first = api.record_audit_event(
        LedgerApiAuditEventRequest(
            event_name="client_error",
            related_id="opp_001",
            payload={"message": "timeout"},
            idempotency_key="audit:test",
        )
    )
    second = api.record_audit_event(
        LedgerApiAuditEventRequest(
            event_name="client_error",
            related_id="opp_001",
            payload={"message": "timeout"},
            idempotency_key="audit:test",
        )
    )

    assert first.ledger_event_id == second.ledger_event_id


def test_event_log_filters_typed_events(tmp_path: Path) -> None:
    api = make_api(tmp_path)
    api.record_audit_event(
        LedgerApiAuditEventRequest(
            event_name="client_error",
            related_id="opp_001",
            payload={"message": "timeout"},
            idempotency_key="audit:filter",
        )
    )

    events = api.get_event_log(related_type=RecordType.AUDIT_EVENT)

    assert events
