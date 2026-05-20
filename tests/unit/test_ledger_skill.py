"""Tests for the ledger skill implementation."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from openclaw_moneybot.shared import (
    BudgetPlan,
    EmailDraftRecord,
    EvidenceRecord,
    ExperimentReview,
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
    SpendRequestStatus,
    TosDecisionType,
    WalletTransactionStatus,
)
from openclaw_moneybot.skills.ledger_skill.repository import LedgerRepository


@pytest.fixture()
def repository(tmp_path: Path) -> LedgerRepository:
    repo = LedgerRepository(tmp_path / "moneybot.sqlite3")
    repo.migrate()
    return repo


def make_opportunity(created_at: datetime) -> Opportunity:
    return Opportunity(
        created_at=created_at,
        opportunity_id="opp_001",
        name="OSS bounty",
        category="bounty",
        status="discovered",
        source_url="https://example.com/opportunity",
        rules_url="https://example.com/rules",
        required_spend_usd=0,
        estimated_revenue_usd=25,
        max_loss_usd=0,
        summary="Test opportunity",
    )


def make_policy(created_at: datetime) -> PolicyDecision:
    return PolicyDecision(
        created_at=created_at,
        policy_decision_id="policy_001",
        opportunity_id="opp_001",
        decision=PolicyDecisionType.ALLOW,
        risk_level=RiskLevel.LOW,
        confidence=ConfidenceLevel.HIGH,
        matched_rules=["safe_research"],
        policy_version="v1",
        request_fingerprint="req_hash",
    )


def make_tos_check(created_at: datetime) -> TosLegalCheck:
    return TosLegalCheck(
        created_at=created_at,
        tos_legal_check_id="tos_001",
        opportunity_id="opp_001",
        decision=TosDecisionType.PROCEED,
        confidence=ConfidenceLevel.HIGH,
        platform_terms_summary="Terms allow submissions.",
        legal_risk_summary="No obvious legal risk.",
        tos_risk_summary="Low risk.",
        evidence_archive_ids=["artifact_001"],
    )


def make_budget_plan(created_at: datetime) -> BudgetPlan:
    return BudgetPlan(
        created_at=created_at,
        budget_plan_id="budget_001",
        opportunity_id="opp_001",
        policy_decision_id="policy_001",
        tos_legal_check_id="tos_001",
        decision=BudgetDecisionType.EXECUTE_REQUEST,
        recommended_budget_usd=5,
        max_loss_usd=5,
        expected_gross_revenue_usd=20,
        expected_net_revenue_usd=15,
        break_even_condition="One accepted bounty.",
        success_metric="Accepted submission",
        stop_condition="Stop after one rejection.",
        required_records=["receipt"],
        risk_level=RiskLevel.LOW,
        wallet_spend_request_allowed=True,
    )


def make_spend_request(created_at: datetime) -> SpendRequest:
    return SpendRequest(
        created_at=created_at,
        spend_request_id="spend_001",
        opportunity_id="opp_001",
        experiment_id="exp_001",
        budget_plan_id="budget_001",
        policy_decision_id="policy_001",
        ledger_record_id="ledger_prewrite_001",
        amount_usd=5,
        asset="BTC",
        destination="bc1testdestination",
        counterparty="Example registrar",
        purpose="Buy domain",
        category="infrastructure",
        evidence_archive_ids=["artifact_001"],
    )


def make_wallet_transaction(created_at: datetime) -> WalletTransactionRecord:
    return WalletTransactionRecord(
        created_at=created_at,
        wallet_transaction_id="wallet_tx_001",
        spend_request_id="spend_001",
        txid="txid_001",
        amount_btc="0.00010000",
        fee_btc="0.00000100",
        amount_usd_estimate=5,
        status="sent",
        destination="bc1testdestination",
        purpose="Buy domain",
    )


def make_evidence(created_at: datetime) -> EvidenceRecord:
    return EvidenceRecord(
        created_at=created_at,
        evidence_id="artifact_001",
        related_record_type=RecordType.OPPORTUNITY,
        related_record_id="opp_001",
        evidence_type="html_snapshot",
        archive_path="archive/2026/01/01/artifact_001.html",
        content_sha256="a" * 64,
        source_url="https://example.com/opportunity",
    )


def make_email(created_at: datetime) -> EmailDraftRecord:
    return EmailDraftRecord(
        created_at=created_at,
        email_draft_id="email_001",
        opportunity_id="opp_001",
        to="owner@example.com",
        subject="Hello",
        body="This is a draft",
    )


def make_review(created_at: datetime) -> ExperimentReview:
    return ExperimentReview(
        created_at=created_at,
        experiment_review_id="review_001",
        opportunity_id="opp_001",
        spent_usd=5,
        revenue_usd=20,
        net_usd=15,
        roi_percent=300,
        outcome="success",
        decision=ReviewDecisionType.CONTINUE,
        lessons=["Works well"],
        recommended_next_actions=["Scale carefully"],
    )


def test_migration_creates_core_tables(repository: LedgerRepository) -> None:
    with sqlite3.connect(repository.db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    table_names = {row[0] for row in rows}
    assert {
        "schema_version",
        "opportunities",
        "policy_decisions",
        "tos_legal_checks",
        "budget_plans",
        "spend_requests",
        "btc_transactions",
        "evidence_records",
        "email_records",
        "experiment_reviews",
        "ledger_events",
    }.issubset(table_names)


def test_repository_operations_round_trip(repository: LedgerRepository, tmp_path: Path) -> None:
    base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    repository.create_opportunity(make_opportunity(base_time))
    repository.record_policy_decision(make_policy(base_time + timedelta(minutes=1)))
    repository.record_tos_legal_check(make_tos_check(base_time + timedelta(minutes=2)))
    repository.record_budget_plan(make_budget_plan(base_time + timedelta(minutes=3)))
    repository.record_spend_request(make_spend_request(base_time + timedelta(minutes=4)))
    repository.record_btc_transaction(make_wallet_transaction(base_time + timedelta(minutes=5)))
    repository.record_evidence(make_evidence(base_time + timedelta(minutes=6)))
    repository.record_email(make_email(base_time + timedelta(minutes=7)))
    repository.record_experiment_review(make_review(base_time + timedelta(minutes=8)))

    timeline = repository.get_opportunity_timeline("opp_001")
    export_result = repository.export_tax_records(tmp_path / "tax" / "records.csv")

    assert len(timeline) == 8
    assert export_result.row_count == 1
    assert export_result.output_path.exists()


def test_foreign_key_constraints_apply(repository: LedgerRepository) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        repository.record_spend_request(
            SpendRequest(
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                spend_request_id="spend_bad",
                opportunity_id="opp_missing",
                budget_plan_id="budget_missing",
                policy_decision_id="policy_missing",
                ledger_record_id="ledger_prewrite_missing",
                amount_usd=1,
                asset="BTC",
                destination="bc1bad",
                counterparty="Missing",
                purpose="Invalid",
                category="infra",
            )
        )


def test_duplicate_txid_rejected(repository: LedgerRepository) -> None:
    base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    repository.create_opportunity(make_opportunity(base_time))
    repository.record_policy_decision(make_policy(base_time + timedelta(minutes=1)))
    repository.record_tos_legal_check(make_tos_check(base_time + timedelta(minutes=2)))
    repository.record_budget_plan(make_budget_plan(base_time + timedelta(minutes=3)))
    repository.record_spend_request(make_spend_request(base_time + timedelta(minutes=4)))
    repository.record_btc_transaction(make_wallet_transaction(base_time + timedelta(minutes=5)))

    with pytest.raises(sqlite3.IntegrityError):
        repository.record_btc_transaction(
            WalletTransactionRecord(
                created_at=base_time + timedelta(minutes=6),
                wallet_transaction_id="wallet_tx_002",
                spend_request_id="spend_001",
                txid="txid_001",
                amount_btc="0.0002",
                fee_btc="0.00000100",
                amount_usd_estimate=6,
                status="sent",
                destination="bc1testdestination",
                purpose="Duplicate",
            )
        )


def test_idempotent_repeated_event_reuses_existing_event(repository: LedgerRepository) -> None:
    result_one = repository.create_opportunity(
        make_opportunity(datetime(2026, 1, 1, tzinfo=UTC)),
        idempotency_key="opportunity:opp_001",
    )
    result_two = repository.create_opportunity(
        make_opportunity(datetime(2026, 1, 1, tzinfo=UTC)),
        idempotency_key="opportunity:opp_001",
    )

    assert result_two.reused_existing_event is True
    assert result_one.ledger_event_id == result_two.ledger_event_id


def test_daily_and_weekly_spend_totals(repository: LedgerRepository) -> None:
    base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    repository.create_opportunity(make_opportunity(base_time))
    repository.record_policy_decision(make_policy(base_time + timedelta(minutes=1)))
    repository.record_tos_legal_check(make_tos_check(base_time + timedelta(minutes=2)))
    repository.record_budget_plan(make_budget_plan(base_time + timedelta(minutes=3)))
    repository.record_spend_request(make_spend_request(base_time + timedelta(minutes=4)))
    repository.record_btc_transaction(make_wallet_transaction(base_time + timedelta(minutes=5)))

    assert repository.get_daily_spend_total("2026-01-01") == pytest.approx(5.0)
    assert repository.get_weekly_spend_total("2026-01-01") == pytest.approx(5.0)


def test_experiment_spend_total_and_category_summaries(repository: LedgerRepository) -> None:
    base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    repository.create_opportunity(make_opportunity(base_time))
    repository.record_policy_decision(make_policy(base_time + timedelta(minutes=1)))
    repository.record_tos_legal_check(make_tos_check(base_time + timedelta(minutes=2)))
    repository.record_budget_plan(make_budget_plan(base_time + timedelta(minutes=3)))
    repository.record_spend_request(make_spend_request(base_time + timedelta(minutes=4)))
    repository.record_btc_transaction(make_wallet_transaction(base_time + timedelta(minutes=5)))
    repository.record_spend_request(
        make_spend_request(base_time + timedelta(minutes=6)).model_copy(
            update={
                "spend_request_id": "spend_002",
                "experiment_id": "exp_001",
                "category": "hosting",
                "ledger_record_id": "ledger_prewrite_002",
            }
        )
    )
    repository.record_btc_transaction(
        make_wallet_transaction(base_time + timedelta(minutes=7)).model_copy(
            update={
                "wallet_transaction_id": "wallet_tx_002",
                "spend_request_id": "spend_002",
                "txid": "txid_002",
                "amount_usd_estimate": 3.0,
                "fee_usd_estimate": 0.5,
                "total_usd_estimate": 3.5,
                "status": WalletTransactionStatus.CONFIRMED,
            }
        )
    )
    repository.record_spend_request(
        make_spend_request(base_time + timedelta(minutes=8)).model_copy(
            update={
                "spend_request_id": "spend_003",
                "experiment_id": "exp_001",
                "category": "hosting",
                "ledger_record_id": "ledger_prewrite_003",
                "status": SpendRequestStatus.REJECTED,
            }
        )
    )
    repository.record_btc_transaction(
        make_wallet_transaction(base_time + timedelta(minutes=9)).model_copy(
            update={
                "wallet_transaction_id": "wallet_tx_003",
                "spend_request_id": "spend_003",
                "txid": "txid_003",
                "amount_usd_estimate": 10.0,
                "fee_usd_estimate": 0.5,
                "total_usd_estimate": 10.5,
                "status": WalletTransactionStatus.FAILED,
            }
        )
    )

    experiment_total = repository.get_experiment_spend_total("exp_001")
    by_category = repository.get_spend_by_category(experiment_id="exp_001")

    assert experiment_total.amount_usd == pytest.approx(8.0)
    assert experiment_total.fee_usd == pytest.approx(0.5)
    assert experiment_total.total_usd == pytest.approx(8.5)
    assert {entry.category for entry in by_category} == {"hosting", "infrastructure"}
    assert sum(entry.total_usd for entry in by_category) == pytest.approx(8.5)


def test_hash_chain_verification_detects_tampering(repository: LedgerRepository) -> None:
    repository.create_opportunity(make_opportunity(datetime(2026, 1, 1, tzinfo=UTC)))
    assert repository.verify_event_chain() is True

    with sqlite3.connect(repository.db_path) as connection:
        connection.execute("UPDATE ledger_events SET payload_json = '{}' WHERE rowid = 1")
        connection.commit()

    assert repository.verify_event_chain() is False


def test_export_tax_records_contains_expected_columns(
    repository: LedgerRepository, tmp_path: Path
) -> None:
    base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    repository.create_opportunity(make_opportunity(base_time))
    repository.record_policy_decision(make_policy(base_time + timedelta(minutes=1)))
    repository.record_tos_legal_check(make_tos_check(base_time + timedelta(minutes=2)))
    repository.record_budget_plan(make_budget_plan(base_time + timedelta(minutes=3)))
    repository.record_spend_request(make_spend_request(base_time + timedelta(minutes=4)))
    repository.record_btc_transaction(make_wallet_transaction(base_time + timedelta(minutes=5)))

    export_result = repository.export_tax_records(tmp_path / "tax.csv")
    exported = export_result.output_path.read_text(encoding="utf-8")

    header = (
        "wallet_transaction_id,created_at,txid,amount_btc,fee_btc,"
        "amount_usd_estimate,counterparty,purpose"
    )
    assert header in exported


def test_missing_required_fields_fail_validation() -> None:
    with pytest.raises(ValidationError):
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_invalid",
            name="Invalid",
            category="bounty",
            status="discovered",
            source_url="https://example.com",
            required_spend_usd=0,
            estimated_revenue_usd=5,
            max_loss_usd=-1,
        )
