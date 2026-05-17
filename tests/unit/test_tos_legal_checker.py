"""Tests for the TOS/legal checker."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from openclaw_moneybot.shared import Opportunity
from openclaw_moneybot.shared.types import RiskLevel
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.tos_legal_checker import (
    TosLegalChecker,
    TosLegalCheckRequest,
)


def fixture_text(name: str) -> str:
    path = Path("tests/fixtures/tos_legal") / name
    return path.read_text(encoding="utf-8")


def make_request(**overrides: object) -> TosLegalCheckRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "opportunity_name": "Test opportunity",
        "source_url": "https://example.com/opportunity",
        "rules_url": "https://example.com/rules",
        "proposed_action": "Review and potentially submit to the bounty.",
        "platform_name": "Example",
        "counterparty": "Example",
        "spend_amount_usd": 0,
        "expected_revenue_usd": 25,
        "evidence_text": fixture_text("allowed_bounty.txt"),
        "evidence_archive_ids": ["artifact_001"],
    }
    payload.update(overrides)
    return TosLegalCheckRequest.model_validate(payload)


def make_checker(tmp_path: Path) -> TosLegalChecker:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Test opportunity",
            category="bounty",
            status="discovered",
            source_url="https://example.com/opportunity",
            rules_url="https://example.com/rules",
            required_spend_usd=0,
            estimated_revenue_usd=25,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key="opportunity:opp_001",
    )
    return TosLegalChecker(ledger_service)


def test_clear_allowed_bounty_fixture(tmp_path: Path) -> None:
    checker = make_checker(tmp_path)

    result = checker.evaluate(make_request())

    assert result.decision == "proceed"
    assert result.ledger_record.decision.value == "proceed"


def test_automation_prohibited_fixture_rejects(tmp_path: Path) -> None:
    checker = make_checker(tmp_path)

    result = checker.evaluate(
        make_request(evidence_text=fixture_text("automation_prohibited.txt"))
    )

    assert result.decision == "reject"
    assert result.red_flags


def test_missing_rules_url_needs_review(tmp_path: Path) -> None:
    checker = make_checker(tmp_path)

    result = checker.evaluate(
        make_request(rules_url=None, evidence_text=None, evidence_archive_ids=["artifact_001"])
    )

    assert result.decision == "human_review"


def test_fake_account_requirement_rejects(tmp_path: Path) -> None:
    checker = make_checker(tmp_path)

    result = checker.evaluate(make_request(evidence_text=fixture_text("fake_account.txt")))

    assert result.decision == "reject"


def test_unclear_payment_terms_need_review(tmp_path: Path) -> None:
    checker = make_checker(tmp_path)

    result = checker.evaluate(make_request(evidence_text=fixture_text("unclear_payment.txt")))

    assert result.decision == "human_review"


def test_affiliate_marketing_with_spam_restriction_requires_mitigation(tmp_path: Path) -> None:
    checker = make_checker(tmp_path)

    result = checker.evaluate(
        make_request(evidence_text=fixture_text("affiliate_with_spam.txt"))
    )

    assert result.decision in {"reject", "human_review"}
    assert result.required_mitigations or result.red_flags


def test_regulated_finance_language_is_rejected(tmp_path: Path) -> None:
    checker = make_checker(tmp_path)

    result = checker.evaluate(make_request(evidence_text=fixture_text("regulated_finance.txt")))

    assert result.decision == "reject"


def test_output_includes_evidence_references(tmp_path: Path) -> None:
    checker = make_checker(tmp_path)

    result = checker.evaluate(make_request())

    assert result.evidence_archive_ids == ["artifact_001"]


def test_handoff_to_policy_guard_is_valid(tmp_path: Path) -> None:
    checker = make_checker(tmp_path)

    result = checker.evaluate(make_request())
    metadata = cast(dict[str, object], result.handoff_to_policy_guard["metadata"])

    assert result.handoff_to_policy_guard["action_type"] == "research"
    assert metadata["opportunity_id"] == "opp_001"
