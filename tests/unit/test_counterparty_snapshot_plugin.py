"""Unit tests for the counterparty snapshot plugin."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from openclaw_moneybot.plugins.counterparty_snapshot_plugin import (
    CounterpartySnapshotPlugin,
    CounterpartySnapshotRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, CounterpartySnapshotConfig
from openclaw_moneybot.shared.types import CounterpartyEvidenceTier, SnapshotFreshness
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
) -> CounterpartySnapshotRequest:
    return CounterpartySnapshotRequest(
        opportunity_id="opp_001",
        counterparty_name="Example Vendor",
        source_url=source_url,
        source_category="public_profile",
        content_type="text/plain",
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
