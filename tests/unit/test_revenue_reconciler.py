"""Unit tests for revenue reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import ReconciliationStatus
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.revenue_reconciler import (
    ReconciliationObservation,
    RevenueReconciler,
    RevenueReconciliationRequest,
)


def make_reconciler(tmp_path: Path) -> RevenueReconciler:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    return RevenueReconciler(ArchiveConfig(base_directory=tmp_path / "archive"), ledger_service)


def make_request(**overrides: object) -> RevenueReconciliationRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "expected_amount": 25.0,
        "currency_or_asset": "USD",
        "current_date": datetime(2026, 1, 3, tzinfo=UTC),
        "expected_date": datetime(2026, 1, 2, tzinfo=UTC),
        "expected_counterparty": "Example Counterparty",
        "observations": [
            {
                "observation_id": "obs_001",
                "amount": 25.0,
                "currency_or_asset": "USD",
                "observed_at": datetime(2026, 1, 2, tzinfo=UTC),
                "counterparty": "Example Counterparty",
                "source_type": "email_receipt",
                "evidence_archive_id": "artifact_001",
            }
        ],
    }
    payload.update(overrides)
    return RevenueReconciliationRequest.model_validate(payload)


def test_exact_payout_match_succeeds(tmp_path: Path) -> None:
    result = make_reconciler(tmp_path).reconcile(make_request())

    assert result.status is ReconciliationStatus.MATCHED
    assert result.followup_recommended is False


def test_underpayment_is_detected(tmp_path: Path) -> None:
    result = make_reconciler(tmp_path).reconcile(
        make_request(
            observations=[
                make_request().observations[0].model_copy(update={"amount": 10.0})
            ]
        )
    )

    assert result.status is ReconciliationStatus.UNDERPAID
    assert result.followup_recommended is True


def test_missing_payout_becomes_unresolved(tmp_path: Path) -> None:
    result = make_reconciler(tmp_path).reconcile(make_request(observations=[]))

    assert result.status is ReconciliationStatus.LATE
    assert "late_payout" in result.reason_codes


def test_ambiguous_multiple_receipts_becomes_review_required(tmp_path: Path) -> None:
    first = make_request().observations[0]
    second = ReconciliationObservation.model_validate(
        {
            "observation_id": "obs_002",
            "amount": 25.0,
            "currency_or_asset": "USD",
            "observed_at": datetime(2026, 1, 2, tzinfo=UTC),
            "counterparty": "Example Counterparty",
            "source_type": "wallet_receipt",
            "evidence_archive_id": "artifact_002",
        }
    )
    result = make_reconciler(tmp_path).reconcile(make_request(observations=[first, second]))

    assert result.status is ReconciliationStatus.AMBIGUOUS_NEEDS_REVIEW
    assert result.followup_recommended is True


def test_late_payout_window_is_flagged(tmp_path: Path) -> None:
    request = make_request(observations=[], current_date=datetime(2026, 1, 10, tzinfo=UTC))
    result = make_reconciler(tmp_path).reconcile(request)

    assert result.status is ReconciliationStatus.LATE
