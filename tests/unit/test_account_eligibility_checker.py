"""Unit tests for account eligibility checks."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import EligibilityDecisionType, RecordType
from openclaw_moneybot.skills.account_eligibility_checker import (
    AccountEligibilityChecker,
    AccountEligibilityRequest,
    OperatorProfile,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_checker(tmp_path: Path) -> AccountEligibilityChecker:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    return AccountEligibilityChecker(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )


def make_request(**overrides: object) -> AccountEligibilityRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "opportunity_name": "Allowed opportunity",
        "rules_text": "Open worldwide. BTC payout. Linux required.",
        "source_url": "https://example.com/opportunity",
        "operator_profile": {
            "region": "us",
            "supported_assets": ["btc"],
            "operating_systems": ["linux"],
            "available_hardware": ["gpu"],
            "private_infrastructure_available": True,
            "repository_history_available": True,
            "prior_contribution_tags": ["oss"],
            "profile_reputation_available": True,
        },
    }
    payload.update(overrides)
    return AccountEligibilityRequest.model_validate(payload)


def test_eligible_low_risk_opportunity_passes(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(make_request())

    assert result.decision is EligibilityDecisionType.ELIGIBLE
    assert result.blocked_requirements == []
    assert result.evidence_archive_ids


def test_personal_account_requirement_blocks(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(rules_text="Requires personal account and BTC payout.")
    )

    assert result.decision is EligibilityDecisionType.BLOCKED
    assert "requires_personal_account" in result.blocked_requirements


def test_geo_restriction_blocks(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="US only. BTC payout.",
            operator_profile={"region": "canada", "supported_assets": ["btc"]},
        )
    )

    assert result.decision is EligibilityDecisionType.BLOCKED
    assert "geo_restriction" in result.blocked_requirements


def test_unsupported_payout_method_blocks(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Payout via PayPal only.",
            operator_profile={"supported_assets": ["btc"]},
        )
    )

    assert result.decision is EligibilityDecisionType.BLOCKED
    assert "unsupported_payout_method" in result.blocked_requirements


def test_ambiguous_requirement_becomes_needs_review(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Requires tax form and KYC.",
            operator_profile=OperatorProfile(supported_assets=["btc"]),
        )
    )

    assert result.decision is EligibilityDecisionType.NEEDS_REVIEW
    assert "tax_or_kyc_unverified" in result.review_required_requirements


def test_missing_rule_text_becomes_incomplete(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(make_request(rules_text=None))

    assert result.decision is EligibilityDecisionType.INCOMPLETE
    assert "missing_rule_text" in result.missing_requirements
    assert result.ledger_record.record_type is RecordType.ACCOUNT_ELIGIBILITY
