"""Unit tests for the counterparty snapshot plugin."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from openclaw_moneybot.plugins.counterparty_snapshot_plugin import (
    CounterpartySnapshotPlugin,
    CounterpartySnapshotRequest,
)
from openclaw_moneybot.plugins.counterparty_snapshot_plugin.service import (
    _bool_field,
    _changed_fields,
    _evidence_tier,
    _extract_indicators,
    _freshness_for,
    _int_field,
    _parse_bool,
    _parse_public_fields,
    _string_field,
)
from openclaw_moneybot.shared import ArchiveConfig, CounterpartySnapshotConfig, LedgerRecord
from openclaw_moneybot.shared.types import CounterpartyEvidenceTier, RecordType, SnapshotFreshness
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(tmp_path: Path) -> CounterpartySnapshotPlugin:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    return CounterpartySnapshotPlugin(
        CounterpartySnapshotConfig(
            enabled=True,
            allowed_hosts=["example.com"],
            freshness_days=30,
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )


def make_request(
    *,
    content_text: str,
    captured_at: datetime | None = None,
    current_time: datetime | None = None,
    source_url: str = "https://example.com/public/profile",
    source_category: str = "public_profile",
    content_type: str = "text/plain",
) -> CounterpartySnapshotRequest:
    return CounterpartySnapshotRequest(
        opportunity_id="opp_001",
        counterparty_name="Example Vendor",
        source_url=source_url,
        source_category=source_category,
        content_type=content_type,
        content_text=content_text,
        captured_at=captured_at or datetime(2026, 1, 1, tzinfo=UTC),
        current_time=current_time,
    )


def test_supported_public_snapshot_capture_succeeds(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    result = plugin.capture(
        make_request(
            content_text=(
                "display_name: Example Vendor\n"
                "support_email: support@example.com\n"
                "payout_terms_present: yes\n"
                "payment_proof_present: yes\n"
                "dispute_policy_present: yes\n"
            ),
            current_time=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )

    assert result.freshness is SnapshotFreshness.FRESH
    assert result.evidence_tier is CounterpartyEvidenceTier.STRONG
    assert result.indicators["support_email"] == "support@example.com"
    assert len(result.evidence_archive_ids) == 2


def test_non_allowlisted_source_is_rejected(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="not allowlisted"):
        plugin.capture(
            make_request(
                content_text="display_name: Example Vendor",
                source_url="https://forbidden.example.org/public/profile",
            )
        )


def test_missing_expected_fields_are_surfaced_as_incomplete(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    result = plugin.capture(
        make_request(
            content_text="display_name: Example Vendor\nsupport_email: support@example.com\n",
            current_time=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )

    assert "payment_proof_present" in result.missing_fields
    assert result.evidence_tier is CounterpartyEvidenceTier.PARTIAL


def test_freshness_metadata_is_preserved(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    result = plugin.capture(
        make_request(
            content_text="display_name: Example Vendor\nsupport_email: support@example.com\n",
            captured_at=datetime(2025, 10, 1, tzinfo=UTC),
            current_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    assert result.freshness is SnapshotFreshness.STALE


def test_repeated_capture_comparison_behaves_deterministically(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    request = make_request(
        content_text=(
            "display_name: Example Vendor\n"
            "support_email: support@example.com\n"
            "payout_terms_present: yes\n"
            "payment_proof_present: yes\n"
        ),
        current_time=datetime(2026, 1, 2, tzinfo=UTC),
    )

    first = plugin.capture(request)
    second = plugin.capture(request)

    assert first.changed_fields
    assert second.previous_snapshot_id == first.snapshot_id
    assert second.changed_fields == []


def test_unsupported_source_category_is_rejected(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="Unsupported source category"):
        plugin.capture(
            make_request(content_text="display_name: Example", source_category="private")
        )


def test_non_allowlisted_content_type_is_rejected(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="content type"):
        plugin.capture(
            make_request(
                content_text="display_name: Example",
                content_type="application/json",
            )
        )


def test_oversized_content_is_rejected(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    plugin.config.max_content_bytes = 10

    with pytest.raises(ValueError, match="size limit"):
        plugin.capture(make_request(content_text="display_name: Example Vendor"))


def test_private_path_is_rejected(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="public pages"):
        plugin.capture(
            make_request(
                content_text="display_name: Example",
                source_url="https://example.com/login/profile",
            )
        )


def test_robots_disallowed_rejects_capture(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="disallowed"):
        plugin.capture(
            make_request(
                content_text="display_name: Example Vendor\nrobots_allowed: no\n",
            )
        )


def test_find_previous_snapshot_ignores_malformed_and_unrelated_entries(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    ledger_service = plugin.ledger_service
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            record_id="bad_snapshot",
            record_type=RecordType.COUNTERPARTY_SNAPSHOT,
            related_record_id="opp_001",
            payload={"payload": "bad"},
        ),
        idempotency_key="bad_snapshot",
    )
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            record_id="other_snapshot",
            record_type=RecordType.COUNTERPARTY_SNAPSHOT,
            related_record_id="opp_001",
            payload={
                "snapshot_id": "other_snapshot",
                "counterparty_name": "Other Vendor",
                "source_category": "public_profile",
                "captured_at": "2026-01-02T00:00:00+00:00",
            },
        ),
        idempotency_key="other_snapshot",
    )
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=datetime(2026, 1, 3, tzinfo=UTC),
            record_id="good_snapshot",
            record_type=RecordType.COUNTERPARTY_SNAPSHOT,
            related_record_id="opp_001",
            payload={
                "snapshot_id": "good_snapshot",
                "counterparty_name": "Example Vendor",
                "source_category": "public_profile",
                "captured_at": "2026-01-03T00:00:00+00:00",
                "indicators": {"display_name": "Example Vendor"},
            },
        ),
        idempotency_key="good_snapshot",
    )

    previous = plugin._find_previous_snapshot(
        counterparty_name="Example Vendor",
        source_category="public_profile",
    )

    assert previous is not None
    assert previous["snapshot_id"] == "good_snapshot"


def test_changed_fields_returns_all_fields_for_malformed_prior_indicators() -> None:
    assert _changed_fields({"indicators": "bad"}, {"a": 1, "b": 2}) == ["a", "b"]


def test_parse_public_fields_ignores_blank_lines_and_missing_separators() -> None:
    parsed = _parse_public_fields(
        "display_name: Example\n\nnonsense line\nsupport_email=support@example.com"
    )

    assert parsed["display_name"] == "Example"
    assert parsed["support_email"] == "support@example.com"
    assert "nonsense line" not in parsed


def test_parse_public_fields_supports_digit_and_boolean_normalization() -> None:
    parsed = _parse_public_fields(
        "domain_age_days: 365\npayment_proof_present: yes\nrobots_allowed: no"
    )

    assert parsed["domain_age_days"] == 365
    assert parsed["payment_proof_present"] is True
    assert parsed["robots_allowed"] is False


def test_extract_indicators_falls_back_to_counterparty_name_and_strips_invalid_email() -> None:
    indicators = _extract_indicators(
        {"support_email": "not-an-email", "domain_age_days": 10},
        "Example Vendor",
        "example.com",
    )

    assert indicators["display_name"] == "Example Vendor"
    assert indicators["support_email"] is None
    assert indicators["domain_age_days"] == 10


@pytest.mark.parametrize(
    ("expected_count", "missing_count", "expected_tier"),
    [
        (4, 4, CounterpartyEvidenceTier.INCOMPLETE),
        (4, 0, CounterpartyEvidenceTier.STRONG),
        (4, 1, CounterpartyEvidenceTier.PARTIAL),
        (4, 3, CounterpartyEvidenceTier.WEAK),
    ],
)
def test_evidence_tier_thresholds(
    expected_count: int,
    missing_count: int,
    expected_tier: CounterpartyEvidenceTier,
) -> None:
    assert _evidence_tier(
        expected_count=expected_count,
        missing_count=missing_count,
    ) is expected_tier


def test_freshness_unknown_when_current_time_missing() -> None:
    assert (
        _freshness_for(
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
            current_time=None,
            freshness_days=30,
        )
        is SnapshotFreshness.UNKNOWN
    )


def test_parse_bool_returns_none_for_unrecognized_values() -> None:
    assert _parse_bool("maybe") is None


def test_helper_type_extractors_reject_wrong_types() -> None:
    assert _bool_field("yes") is None
    assert _int_field("10") is None
    assert _string_field(1) is None
