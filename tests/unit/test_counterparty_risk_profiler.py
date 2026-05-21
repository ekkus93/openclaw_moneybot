"""Unit tests for counterparty risk profiling."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import CounterpartyRiskTier
from openclaw_moneybot.skills.counterparty_risk_profiler import (
    CounterpartyRiskProfiler,
    CounterpartyRiskProfileRequest,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_profiler(tmp_path: Path) -> CounterpartyRiskProfiler:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    return CounterpartyRiskProfiler(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )


def make_request(**overrides: object) -> CounterpartyRiskProfileRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "counterparty_name": "Example Counterparty",
        "platform_domain": "example.com",
        "payout_history_success_rate": 0.9,
        "clear_payout_rules": True,
        "clear_deadlines": True,
    }
    payload.update(overrides)
    return CounterpartyRiskProfileRequest.model_validate(payload)


def test_positive_history_lowers_risk(tmp_path: Path) -> None:
    result = make_profiler(tmp_path).profile(make_request())

    assert result.risk_tier is CounterpartyRiskTier.LOW


def test_missing_payout_proof_raises_risk(tmp_path: Path) -> None:
    result = make_profiler(tmp_path).profile(
        make_request(payout_history_success_rate=0.3, clear_payout_rules=False)
    )

    assert result.risk_tier is not CounterpartyRiskTier.LOW


def test_suspicious_off_platform_payment_raises_risk(tmp_path: Path) -> None:
    result = make_profiler(tmp_path).profile(
        make_request(off_platform_payment_required=True, suspicious_claims_present=True)
    )

    assert result.risk_tier is CounterpartyRiskTier.HIGH


def test_unknown_data_does_not_silently_produce_low_risk(tmp_path: Path) -> None:
    result = make_profiler(tmp_path).profile(
        make_request(
            payout_history_success_rate=None,
            support_responsive=None,
            clear_payout_rules=False,
        )
    )

    assert result.risk_tier is not CounterpartyRiskTier.LOW
