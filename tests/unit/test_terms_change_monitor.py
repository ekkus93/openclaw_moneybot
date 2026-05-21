"""Unit tests for terms-change monitoring."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import TermsChangeSeverity
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.terms_change_monitor import (
    TermsChangeMonitor,
    TermsChangeMonitorRequest,
)


def make_monitor(tmp_path: Path) -> TermsChangeMonitor:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    return TermsChangeMonitor(ArchiveConfig(base_directory=tmp_path / "archive"), ledger_service)


def make_request(**overrides: object) -> TermsChangeMonitorRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "prior_rules_text": "Payout $25.\nDeadline: 2026-01-02.\nAutomation allowed.",
        "current_rules_text": "Payout $25. Deadline: 2026-01-02. Automation allowed.",
    }
    payload.update(overrides)
    return TermsChangeMonitorRequest.model_validate(payload)


def test_formatting_only_change_stays_low_severity(tmp_path: Path) -> None:
    result = make_monitor(tmp_path).evaluate(
        make_request(current_rules_text="Payout $25.\n\nDeadline: 2026-01-02.\nAutomation allowed.")
    )

    assert result.severity is TermsChangeSeverity.LOW
    assert "formatting_only" in result.changed_fields


def test_payout_reduction_triggers_budget_recheck(tmp_path: Path) -> None:
    result = make_monitor(tmp_path).evaluate(
        make_request(current_rules_text="Payout $10.\nDeadline: 2026-01-02.\nAutomation allowed.")
    )

    assert result.requires_budget_recheck is True
    assert "payout_amount" in result.changed_fields


def test_bot_prohibition_triggers_block_severity(tmp_path: Path) -> None:
    result = make_monitor(tmp_path).evaluate(
        make_request(current_rules_text="Payout $25.\nAutomation prohibited. No bots.")
    )

    assert result.severity is TermsChangeSeverity.BLOCK
    assert "automation_policy" in result.changed_fields


def test_deadline_change_triggers_review(tmp_path: Path) -> None:
    result = make_monitor(tmp_path).evaluate(
        make_request(current_rules_text="Payout $25.\nDeadline: 2026-02-01.\nAutomation allowed.")
    )

    assert result.requires_recheck is True
    assert "submission_deadline" in result.changed_fields


def test_missing_old_snapshot_fails_closed(tmp_path: Path) -> None:
    result = make_monitor(tmp_path).evaluate(make_request(prior_rules_text=None))

    assert result.requires_recheck is True
    assert result.severity is TermsChangeSeverity.HIGH
    assert "missing_prior_snapshot" in result.changed_fields


def test_malformed_prior_snapshot_text_falls_back_safely(tmp_path: Path) -> None:
    result = make_monitor(tmp_path).evaluate(
        make_request(prior_rules_text="   ", prior_budget_plan_id="budget_001")
    )

    assert result.severity is TermsChangeSeverity.HIGH
    assert result.requires_budget_recheck is True
    assert result.requires_policy_recheck is True


def test_identical_rules_yield_no_change_severity(tmp_path: Path) -> None:
    current = "Payout $25.\nDeadline: 2026-01-02.\nAutomation allowed."
    result = make_monitor(tmp_path).evaluate(
        make_request(prior_rules_text=current, current_rules_text=current)
    )

    assert result.change_detected is False
    assert result.severity is TermsChangeSeverity.NONE
    assert result.summary == "No material changes detected."


def test_blocking_phrase_wins_over_other_legal_risk_changes(tmp_path: Path) -> None:
    result = make_monitor(tmp_path).evaluate(
        make_request(
            current_rules_text=(
                "Payout $25.\nDeadline: 2026-01-02.\n"
                "Automation prohibited. No bots. KYC required."
            )
        )
    )

    assert result.severity is TermsChangeSeverity.BLOCK
    assert "automation_policy" in result.changed_fields
    assert "kyc_tax_requirement" in result.changed_fields


def test_summary_and_reasons_stay_deterministic_for_nonblocking_changes(tmp_path: Path) -> None:
    result = make_monitor(tmp_path).evaluate(
        make_request(
            current_rules_text=(
                "Payout $25.\nDeadline: 2026-02-01.\nAutomation allowed.\n"
                "Payout by PayPal only.\nRefunds may apply."
            )
        )
    )

    assert result.changed_fields == [
        "payout_method",
        "submission_deadline",
        "refund_chargeback",
    ]
    assert result.summary == (
        "Detected payout_method, submission_deadline, refund_chargeback "
        "changes with medium severity."
    )
