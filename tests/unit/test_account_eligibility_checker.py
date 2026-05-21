"""Unit tests for account eligibility checks."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def make_profile(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "region": "us",
        "supported_assets": ["btc"],
        "supported_payout_methods": ["paypal"],
        "operating_systems": ["linux"],
        "available_hardware": ["gpu"],
        "private_infrastructure_available": True,
        "repository_history_available": True,
        "prior_contribution_tags": ["oss"],
        "profile_reputation_available": True,
        "platform_account_age_days": 90,
        "age_years": 30,
        "has_business_entity": True,
        "tax_identity_available": True,
    }
    payload.update(overrides)
    return payload


def make_request(**overrides: object) -> AccountEligibilityRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "opportunity_name": "Allowed opportunity",
        "rules_text": "Open worldwide. BTC payout. Linux required.",
        "source_url": "https://example.com/opportunity",
        "operator_profile": make_profile(),
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


@pytest.mark.parametrize(
    ("rules_text", "profile_overrides", "expected_code"),
    [
        (
            "Requires non-bot social identity.",
            {"non_bot_social_identity_available": False},
            "requires_non_bot_social_identity",
        ),
        (
            "Account age must be 30 days.",
            {"platform_account_age_days": None},
            "platform_account_age_unknown",
        ),
        (
            "Account age must be 30 days.",
            {"platform_account_age_days": 10},
            "platform_account_too_new",
        ),
        (
            "Strong karma and rating history required.",
            {"profile_reputation_available": None},
            "reputation_requirement_unverified",
        ),
        (
            "Strong karma and rating history required.",
            {"profile_reputation_available": False},
            "missing_required_reputation_history",
        ),
        ("EU only.", {"region": None, "residency": None, "citizenship": None}, "region_unknown"),
        ("EU only.", {"region": "us"}, "geo_restriction"),
        ("Must be 18+.", {"age_years": None}, "age_unknown"),
        ("Must be 18+.", {"age_years": 17}, "age_restriction"),
        (
            "Registered business entity required.",
            {"has_business_entity": None},
            "business_entity_unknown",
        ),
        (
            "Registered business entity required.",
            {"has_business_entity": False},
            "business_entity_required",
        ),
        ("Requires W-9 and KYC.", {"tax_identity_available": False}, "tax_or_kyc_requirement"),
        (
            "Requires private VPS access.",
            {"private_infrastructure_available": None},
            "private_infrastructure_unverified",
        ),
        (
            "Requires private VPS access.",
            {"private_infrastructure_available": False},
            "private_infrastructure_required",
        ),
        (
            "Requires GitHub history.",
            {"repository_history_available": None},
            "repository_history_unknown",
        ),
        (
            "Requires GitHub history.",
            {"repository_history_available": False},
            "repository_history_required",
        ),
        (
            "Requires prior contribution.",
            {"prior_contribution_tags": []},
            "prior_contribution_required",
        ),
        ("Windows required.", {"operating_systems": ["linux"]}, "windows_required"),
        ("iPhone required.", {"available_hardware": ["gpu"]}, "iphone_required"),
        ("Bitcoin payout only.", {"supported_assets": ["usd"]}, "unsupported_currency_or_asset"),
        ("Payment approval required before payout.", {}, "manual_payment_approval_needed"),
    ],
)
def test_account_eligibility_branch_matrix(
    tmp_path: Path,
    *,
    rules_text: str,
    profile_overrides: dict[str, object],
    expected_code: str,
) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text=rules_text,
            operator_profile=make_profile(**profile_overrides),
        )
    )

    combined = [
        *result.blocked_requirements,
        *result.missing_requirements,
        *result.review_required_requirements,
    ]
    assert expected_code in combined


def test_geo_allowed_region_does_not_add_geo_failure_codes(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="EU only. Bitcoin payout. Linux required.",
            operator_profile=make_profile(region="eu"),
        )
    )

    assert "geo_restriction" not in result.blocked_requirements
    assert "region_unknown" not in result.missing_requirements


def test_citizenship_requirement_without_geo_phrase_needs_review(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Citizen or resident required.",
            operator_profile=make_profile(),
        )
    )

    assert result.decision is EligibilityDecisionType.NEEDS_REVIEW
    assert "citizenship_or_residency_requirement" in result.review_required_requirements


def test_age_requirement_passes_when_age_is_sufficient(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Must be 18+. Linux required. Bitcoin payout.",
            operator_profile=make_profile(age_years=18),
        )
    )

    assert result.decision is EligibilityDecisionType.ELIGIBLE


def test_tax_requirement_needs_review_when_identity_unverified(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Requires tax form and W-9.",
            operator_profile=make_profile(tax_identity_available=None),
        )
    )

    assert result.decision is EligibilityDecisionType.NEEDS_REVIEW
    assert "tax_or_kyc_unverified" in result.review_required_requirements


def test_unsupported_payout_method_from_text_blocks(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Bank wire only.",
            operator_profile=make_profile(supported_payout_methods=["paypal"]),
        )
    )

    assert result.decision is EligibilityDecisionType.BLOCKED
    assert "unsupported_payout_method" in result.blocked_requirements


def test_payment_method_hint_can_trigger_payout_method_block(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Fast payout available.",
            payment_method_hint="bank wire",
            operator_profile=make_profile(supported_payout_methods=["paypal"]),
        )
    )

    assert result.decision is EligibilityDecisionType.BLOCKED
    assert "unsupported_payout_method" in result.blocked_requirements


def test_asset_hint_can_trigger_asset_block(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Fast payout available.",
            asset_hint="eth",
            operator_profile=make_profile(supported_assets=["btc"]),
        )
    )

    assert result.decision is EligibilityDecisionType.BLOCKED
    assert "unsupported_currency_or_asset" in result.blocked_requirements


def test_blocked_requirements_take_priority_over_review_and_missing(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Requires personal account, W-9, and account age 30 days.",
            operator_profile=make_profile(
                personal_account_allowed=False,
                tax_identity_available=None,
                platform_account_age_days=None,
            ),
        )
    )

    assert result.decision is EligibilityDecisionType.BLOCKED
    assert result.reasons == [
        "Eligibility requirements conflict with the configured operator profile."
    ]
    assert result.safe_next_steps == ["record_block_and_skip_budgeting"]


def test_review_required_without_blocks_returns_needs_review(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Requires private infrastructure access.",
            operator_profile=make_profile(private_infrastructure_available=None),
        )
    )

    assert result.decision is EligibilityDecisionType.NEEDS_REVIEW
    assert result.reasons == ["Some requirements are ambiguous or require manual confirmation."]


def test_missing_only_scenario_returns_incomplete(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Account age must be 30 days.",
            operator_profile=make_profile(platform_account_age_days=None),
        )
    )

    assert result.decision is EligibilityDecisionType.INCOMPLETE
    assert result.reasons == [
        "Eligibility evidence is missing for one or more required checks."
    ]


def test_clean_supported_scenario_returns_eligible(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            rules_text="Linux required. Bitcoin payout. Account age must be 30 days.",
            operator_profile=make_profile(platform_account_age_days=45),
        )
    )

    assert result.decision is EligibilityDecisionType.ELIGIBLE
    assert result.reasons == [
        "The opportunity requirements are compatible with the configured operator profile."
    ]
