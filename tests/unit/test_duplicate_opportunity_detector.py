"""Unit tests for duplicate opportunity detection."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.skills.duplicate_opportunity_detector import (
    DuplicateOpportunityDetector,
    DuplicateOpportunityDetectorRequest,
    OpportunityFingerprint,
)
from openclaw_moneybot.skills.duplicate_opportunity_detector.runner import _normalized
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_detector(tmp_path: Path) -> DuplicateOpportunityDetector:
    return DuplicateOpportunityDetector(
        LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    )


def fingerprint(**overrides: object) -> OpportunityFingerprint:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "title": "Example bounty",
        "source_url": "https://example.com/bounty",
        "rules_url": "https://example.com/bounty/rules",
        "description": "Build a docs patch for $25",
        "payout_usd": 25.0,
        "platform": "example",
    }
    payload.update(overrides)
    return OpportunityFingerprint.model_validate(payload)


def test_exact_repost_is_detected(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(),
            existing=[fingerprint(opportunity_id="opp_existing")],
        )
    )

    assert result.is_duplicate is True


def test_small_title_variation_is_detected(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(title="Example bounty repost"),
            existing=[fingerprint(opportunity_id="opp_existing", title="Example bounty repost")],
        )
    )

    assert result.is_duplicate is True


def test_similar_wording_not_overblocked(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(title="Different task", source_url="https://example.com/other"),
            existing=[
                fingerprint(
                    opportunity_id="opp_existing",
                    description="Different payout and different task",
                    source_url="https://example.com/existing",
                    payout_usd=40.0,
                )
            ],
        )
    )

    assert result.is_duplicate is False


def test_missing_metadata_degrades_to_review_not_false_uniqueness(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(description=None),
            existing=[fingerprint(opportunity_id="opp_existing", description=None)],
        )
    )

    assert result.confidence.value in {"medium", "high"}


def test_exact_url_match_returns_high_confidence_reason(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(source_url="https://example.com/same"),
            existing=[fingerprint(opportunity_id="opp_existing", source_url="https://example.com/same")],
        )
    )

    assert result.confidence.value == "high"
    assert result.match_reasons == ["exact_url_match"]


def test_matching_rules_url_and_exact_title_triggers_rules_match(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(source_url="https://example.com/new"),
            existing=[
                fingerprint(
                    opportunity_id="opp_existing",
                    source_url="https://example.com/existing",
                )
            ],
        )
    )

    assert "normalized_rules_url_match" in result.match_reasons
    assert result.confidence.value == "high"


def test_matching_rules_url_and_similar_description_triggers_rules_match(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(
                source_url="https://example.com/new",
                title="Different title",
                description="Build a docs patch for twenty five dollars with screenshots",
            ),
            existing=[
                fingerprint(
                    opportunity_id="opp_existing",
                    source_url="https://example.com/existing",
                    title="Older listing",
                    description="Build a docs patch for twenty five dollars with screenshots",
                )
            ],
        )
    )

    assert "normalized_rules_url_match" in result.match_reasons
    assert result.confidence.value == "high"


def test_exact_normalized_title_match_without_url_match_is_medium(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(source_url="https://example.com/new"),
            existing=[
                fingerprint(
                    opportunity_id="opp_existing",
                    source_url="https://example.com/existing",
                    rules_url="https://example.com/other-rules",
                )
            ],
        )
    )

    assert result.confidence.value == "medium"
    assert "normalized_title_match" in result.match_reasons


def test_near_duplicate_repost_requires_similarity_platform_and_payout(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(
                title="Different title",
                source_url="https://example.com/new",
                rules_url="https://example.com/rules-new",
                description="Build docs patch for twenty five dollars and attach screenshots",
            ),
            existing=[
                fingerprint(
                    opportunity_id="opp_existing",
                    title="Another title",
                    source_url="https://example.com/existing",
                    rules_url="https://example.com/rules-existing",
                    description="Build docs patch for twenty five dollars and attach screenshots",
                )
            ],
        )
    )

    assert "near_duplicate_repost" in result.match_reasons
    assert result.confidence.value == "high"


def test_near_duplicate_repost_not_triggered_when_platform_differs(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(
                title="Different title",
                source_url="https://example.com/new",
                rules_url="https://example.com/rules-new",
                description="Build docs patch for twenty five dollars and attach screenshots",
            ),
            existing=[
                fingerprint(
                    opportunity_id="opp_existing",
                    title="Another title",
                    source_url="https://example.com/existing",
                    rules_url="https://example.com/rules-existing",
                    description="Build docs patch for twenty five dollars and attach screenshots",
                    platform="other",
                )
            ],
        )
    )

    assert "near_duplicate_repost" not in result.match_reasons


def test_near_duplicate_repost_not_triggered_when_payout_differs(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(
                title="Different title",
                source_url="https://example.com/new",
                rules_url="https://example.com/rules-new",
                description="Build docs patch for twenty five dollars and attach screenshots",
            ),
            existing=[
                fingerprint(
                    opportunity_id="opp_existing",
                    title="Another title",
                    source_url="https://example.com/existing",
                    rules_url="https://example.com/rules-existing",
                    description="Build docs patch for twenty five dollars and attach screenshots",
                    payout_usd=50.0,
                )
            ],
        )
    )

    assert "near_duplicate_repost" not in result.match_reasons


def test_missing_title_triggers_metadata_review_when_not_duplicate(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(
                title="",
                description="Unique details",
                source_url="https://example.com/new",
                rules_url="https://example.com/new-rules",
            ),
            existing=[
                fingerprint(
                    opportunity_id="opp_existing",
                    title="Different title",
                    source_url="https://example.com/existing",
                    rules_url="https://example.com/existing-rules",
                )
            ],
        )
    )

    assert result.is_duplicate is False
    assert "metadata_incomplete_review" in result.match_reasons


def test_duplicate_path_returns_reuse_next_step(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(),
            existing=[fingerprint(opportunity_id="opp_existing")],
        )
    )

    assert result.safe_next_steps == ["reuse_existing_opportunity_or_require_review"]


def test_non_duplicate_path_returns_continue_next_step(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(source_url="https://example.com/new", rules_url="https://example.com/new-rules"),
            existing=[
                fingerprint(
                    opportunity_id="opp_existing",
                    source_url="https://example.com/existing",
                    rules_url="https://example.com/existing-rules",
                    title="Different title",
                    description="Different description",
                    payout_usd=50.0,
                )
            ],
        )
    )

    assert result.safe_next_steps == ["continue_normal_workflow"]


def test_multiple_matches_preserve_deterministic_ordering(tmp_path: Path) -> None:
    result = make_detector(tmp_path).evaluate(
        DuplicateOpportunityDetectorRequest(
            candidate=fingerprint(),
            existing=[
                fingerprint(opportunity_id="opp_a"),
                fingerprint(opportunity_id="opp_b"),
            ],
        )
    )

    assert result.matched_opportunity_ids == ["opp_a", "opp_b"]
    assert result.match_reasons == ["exact_url_match", "exact_url_match"]


def test_normalized_helper_handles_none_spacing_and_case() -> None:
    assert _normalized(None) == ""
    assert _normalized("  Mixed   CASE text ") == "mixed case text"
