"""Integration coverage for the PLUGINS1 Phase C wave."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.plugins.counterparty_snapshot_plugin import (
    CounterpartySnapshotPlugin,
    CounterpartySnapshotRequest,
)
from openclaw_moneybot.plugins.metrics_export_plugin import (
    MetricsExportPlugin,
    MetricsExportRequest,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    BudgetPlan,
    CounterpartySnapshotConfig,
    MetricsExportConfig,
    Opportunity,
    PolicyDecision,
    TosLegalCheck,
)
from openclaw_moneybot.shared.types import (
    ActionType,
    BudgetDecisionType,
    ConfidenceLevel,
    CounterpartyRiskTier,
    PolicyDecisionType,
    ReconciliationStatus,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.counterparty_risk_profiler import (
    CounterpartyRiskProfiler,
    CounterpartyRiskProfileRequest,
)
from openclaw_moneybot.skills.experiment_reviewer import (
    ExperimentReviewer,
    ExperimentReviewRequest,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.revenue_reconciler import (
    ReconciliationObservation,
    RevenueReconciler,
    RevenueReconciliationRequest,
)
from openclaw_moneybot.skills.strategy_memory_summarizer import (
    StrategyMemorySummarizer,
    StrategyMemorySummaryRequest,
)


def seed_opportunity(ledger_service: LedgerService) -> None:
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Integration opportunity",
            category="bounty",
            status="approved",
            source_url="https://example.com/opportunity",
            rules_url="https://example.com/rules",
            required_spend_usd=5,
            estimated_revenue_usd=25,
            max_loss_usd=5,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key="opportunity:opp_001",
    )


def seed_policy_decision(ledger_service: LedgerService) -> None:
    ledger_service.record_policy_decision(
        PolicyDecision(
            created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            policy_decision_id="policy_001",
            opportunity_id="opp_001",
            action_type=ActionType.SPEND,
            category="purchase",
            requires_payment=True,
            requires_wallet_action=True,
            amount_usd=5,
            counterparty="Example Vendor",
            planned_tools=["wallet_governor_client"],
            sanitized_input={"action_type": "spend"},
            decision=PolicyDecisionType.ALLOW,
            risk_level=RiskLevel.LOW,
            confidence=ConfidenceLevel.HIGH,
            policy_version="v1",
            request_fingerprint="fingerprint",
        ),
        idempotency_key="policy:policy_001",
    )


def seed_tos_legal_check(ledger_service: LedgerService) -> None:
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


def seed_budget_plan(ledger_service: LedgerService) -> None:
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
            expected_gross_revenue_usd=25,
            expected_net_revenue_usd=20,
            break_even_condition="One payout",
            success_metric="Paid",
            stop_condition="Stop after one try",
            required_records=["budget_snapshot"],
            risk_level=RiskLevel.LOW,
            wallet_spend_request_allowed=True,
            approved_spend_categories=["purchase"],
            reasons=["Within limits."],
        ),
        idempotency_key="budget:budget_001",
    )


def test_counterparty_snapshot_can_feed_risk_profiling(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = ArchiveConfig(base_directory=tmp_path / "archive")
    seed_opportunity(ledger_service)
    snapshot_plugin = CounterpartySnapshotPlugin(
        CounterpartySnapshotConfig(
            enabled=True,
            allowed_hosts=["example.com"],
        ),
        archive_config,
        ledger_service,
    )
    risk_profiler = CounterpartyRiskProfiler(archive_config, ledger_service)
    snapshot = snapshot_plugin.capture(
        CounterpartySnapshotRequest(
            opportunity_id="opp_001",
            counterparty_name="Example Vendor",
            source_url="https://example.com/public/profile",
            source_category="public_profile",
            content_type="text/plain",
            content_text=(
                "display_name: Example Vendor\n"
                "support_email: support@example.com\n"
                "payout_terms_present: yes\n"
                "payment_proof_present: yes\n"
                "support_responsive: yes\n"
                "domain_age_days: 365\n"
            ),
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
            current_time=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    domain_age_days = snapshot.indicators["domain_age_days"]
    assert isinstance(domain_age_days, int)
    result = risk_profiler.profile(
        CounterpartyRiskProfileRequest(
            opportunity_id="opp_001",
            counterparty_name="Example Vendor",
            platform_domain=str(snapshot.indicators["platform_domain"]),
            payout_history_success_rate=(
                1.0 if snapshot.indicators["payment_proof_present"] else 0.4
            ),
            support_responsive=bool(snapshot.indicators["support_responsive"]),
            clear_payout_rules=bool(snapshot.indicators["payout_terms_present"]),
            clear_deadlines=True,
            suspicious_claims_present=False,
            off_platform_payment_required=False,
            unexpected_kyc_required=False,
            domain_age_days=domain_age_days,
            evidence_archive_ids=snapshot.evidence_archive_ids,
        )
    )

    assert snapshot.evidence_archive_ids
    assert result.risk_tier is CounterpartyRiskTier.LOW


def test_metrics_export_can_summarize_review_and_strategy_outputs(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = ArchiveConfig(base_directory=tmp_path / "archive")
    seed_opportunity(ledger_service)
    seed_policy_decision(ledger_service)
    seed_tos_legal_check(ledger_service)
    seed_budget_plan(ledger_service)
    review = ExperimentReviewer(archive_config, ledger_service).review(
        ExperimentReviewRequest(
            opportunity_id="opp_001",
            budget_plan_id="budget_001",
            review_reason="Completed work",
            current_date=datetime(2026, 1, 3, tzinfo=UTC),
            revenue_usd=20,
            fees_usd=1,
            time_spent_hours=2,
            success_metric_met=True,
            evidence_archive_ids=["artifact_001"],
        )
    )
    reconciliation = RevenueReconciler(archive_config, ledger_service).reconcile(
        RevenueReconciliationRequest(
            opportunity_id="opp_001",
            expected_amount=20,
            currency_or_asset="USD",
            current_date=datetime(2026, 1, 3, tzinfo=UTC),
            observations=[
                ReconciliationObservation(
                    observation_id="obs_001",
                    amount=20,
                    currency_or_asset="USD",
                    observed_at=datetime(2026, 1, 3, tzinfo=UTC),
                    counterparty="Example Vendor",
                    source_type="receipt",
                )
            ],
        )
    )
    StrategyMemorySummarizer(archive_config, ledger_service).summarize(
        StrategyMemorySummaryRequest(
            opportunity_id="opp_001",
            experiment_review_id=review.experiment_review_id,
            scope="global",
            net_usd=review.net_usd,
            roi_percent=review.roi_percent,
            time_spent_hours=review.time_spent_hours,
            reconciliation_status=ReconciliationStatus.MATCHED,
            counterparty_risk_tier=CounterpartyRiskTier.LOW,
            evidence_archive_ids=reconciliation.evidence_archive_ids,
        )
    )
    exporter = MetricsExportPlugin(
        MetricsExportConfig(enabled=True, export_root=tmp_path / "exports"),
        archive_config,
        ledger_service,
    )

    result = exporter.export(
        MetricsExportRequest(
            export_type="strategy_summaries",
            output_format="json",
            opportunity_category="bounty",
        )
    )
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert rows[0]["scope"] == "global"
    assert result.summary["row_count"] == 1
