"""Unit tests for duplicate opportunity detection."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.skills.duplicate_opportunity_detector import (
    DuplicateOpportunityDetector,
    DuplicateOpportunityDetectorRequest,
    OpportunityFingerprint,
)
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
