"""Tests for experiment review."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.shared import (
    ArchiveConfig,
    BudgetPlan,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    TosLegalCheck,
    WalletTransactionRecord,
)
from openclaw_moneybot.shared.types import (
    BudgetDecisionType,
    ConfidenceLevel,
    PolicyDecisionType,
    RecordType,
    ReviewDecisionType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.experiment_reviewer import ExperimentReviewer, ExperimentReviewRequest
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)


def make_reviewer(tmp_path: Path) -> tuple[ExperimentReviewer, LedgerService, str]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archiver = ReceiptAndEvidenceArchiver(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Review test",
            category="bounty",
            status="approved",
            source_url="https://example.com/opportunity",
            rules_url="https://example.com/rules",
            required_spend_usd=0,
            estimated_revenue_usd=50,
            max_loss_usd=8,
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
            recommended_budget_usd=8,
            max_loss_usd=8,
            expected_gross_revenue_usd=50,
            expected_net_revenue_usd=42,
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
    evidence = archiver.archive(
        EvidenceArchiveRequest(
            related_type=RecordType.OPPORTUNITY,
            related_id="opp_001",
            evidence_type="result_note",
            content_text="Outcome evidence",
        )
    )
    reviewer = ExperimentReviewer(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )
    return reviewer, ledger_service, evidence.evidence_id


def record_spend(
    ledger_service: LedgerService,
    *,
    spend_request_id: str,
    amount_usd: float,
) -> None:
    ledger_service.record_spend_request(
        SpendRequest(
            created_at=datetime(2026, 1, 1, 0, 30, tzinfo=UTC),
            spend_request_id=spend_request_id,
            opportunity_id="opp_001",
            budget_plan_id="budget_001",
            policy_decision_id="policy_001",
            ledger_record_id="ledger_001",
            amount_usd=amount_usd,
            asset="BTC",
            destination="bcrt1qmoneybotdest123",
            counterparty="Example Vendor",
            purpose="Test spend",
            category="purchase",
            evidence_archive_ids=["artifact_001"],
        ),
        idempotency_key=f"spend:{spend_request_id}",
    )
    ledger_service.record_wallet_transaction(
        WalletTransactionRecord(
            created_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
            wallet_transaction_id=f"wallet_tx_{spend_request_id}",
            spend_request_id=spend_request_id,
            txid=f"tx_{spend_request_id}",
            amount_btc="0.00010000",
            fee_btc="0.00000250",
            amount_usd_estimate=amount_usd,
            status="sent",
            destination="bcrt1qmoneybotdest123",
            purpose="Test spend",
        ),
        idempotency_key=f"wallet:tx:{spend_request_id}",
    )


def make_request(**overrides: object) -> ExperimentReviewRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "budget_plan_id": "budget_001",
        "review_reason": "completion",
        "current_date": datetime(2026, 1, 2, tzinfo=UTC),
        "revenue_usd": 50.0,
        "time_spent_hours": 2.0,
        "success_metric_met": True,
        "stop_condition_triggered": False,
        "evidence_archive_ids": [],
    }
    payload.update(overrides)
    return ExperimentReviewRequest.model_validate(payload)


def test_profitable_experiment_continues(tmp_path: Path) -> None:
    reviewer, _, evidence_id = make_reviewer(tmp_path)

    result = reviewer.review(make_request(evidence_archive_ids=[evidence_id]))

    assert result.decision is ReviewDecisionType.CONTINUE


def test_no_revenue_and_stop_condition_stops(tmp_path: Path) -> None:
    reviewer, ledger_service, evidence_id = make_reviewer(tmp_path)
    record_spend(ledger_service, spend_request_id="spend_001", amount_usd=5.0)

    result = reviewer.review(
        make_request(
            revenue_usd=0.0,
            success_metric_met=False,
            stop_condition_triggered=True,
            evidence_archive_ids=[evidence_id],
        )
    )

    assert result.decision is ReviewDecisionType.STOP


def test_missing_data_requires_human_review(tmp_path: Path) -> None:
    reviewer, ledger_service, _ = make_reviewer(tmp_path)
    record_spend(ledger_service, spend_request_id="spend_001", amount_usd=5.0)

    result = reviewer.review(make_request(revenue_usd=10.0))

    assert result.status == "insufficient_data"
    assert result.decision is ReviewDecisionType.HUMAN_REVIEW


def test_legal_red_flag_stops(tmp_path: Path) -> None:
    reviewer, _, evidence_id = make_reviewer(tmp_path)

    result = reviewer.review(
        make_request(
            evidence_archive_ids=[evidence_id],
            incident_flags=["legal_red_flag"],
        )
    )

    assert result.decision is ReviewDecisionType.STOP


def test_inconclusive_low_risk_result_retries(tmp_path: Path) -> None:
    reviewer, _, evidence_id = make_reviewer(tmp_path)

    result = reviewer.review(
        make_request(
            revenue_usd=0.0,
            success_metric_met=False,
            evidence_archive_ids=[evidence_id],
        )
    )

    assert result.decision is ReviewDecisionType.RETRY_WITH_CHANGES


def test_budget_exceeded_requires_human_review(tmp_path: Path) -> None:
    reviewer, ledger_service, evidence_id = make_reviewer(tmp_path)
    record_spend(ledger_service, spend_request_id="spend_002", amount_usd=12.0)

    result = reviewer.review(
        make_request(
            revenue_usd=0.0,
            success_metric_met=False,
            evidence_archive_ids=[evidence_id],
        )
    )

    assert result.decision is ReviewDecisionType.HUMAN_REVIEW


def test_feedback_generation(tmp_path: Path) -> None:
    reviewer, _, evidence_id = make_reviewer(tmp_path)

    result = reviewer.review(make_request(evidence_archive_ids=[evidence_id]))

    assert "category_performance" in result.scoring_feedback


def test_ledger_output_written(tmp_path: Path) -> None:
    reviewer, ledger_service, evidence_id = make_reviewer(tmp_path)

    result = reviewer.review(make_request(evidence_archive_ids=[evidence_id]))

    assert ledger_service.get_experiment_review(result.experiment_review_id) is not None
