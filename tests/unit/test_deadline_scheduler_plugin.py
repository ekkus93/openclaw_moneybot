"""Unit tests for the deadline scheduler plugin."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from openclaw_moneybot.plugins.deadline_scheduler_plugin import (
    DeadlineQueryRequest,
    DeadlineScheduleRequest,
    DeadlineSchedulerPlugin,
)
from openclaw_moneybot.shared import DeadlineSchedulerConfig
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(tmp_path: Path) -> DeadlineSchedulerPlugin:
    return DeadlineSchedulerPlugin(
        DeadlineSchedulerConfig(
            enabled=True,
            schedule_path=tmp_path / "deadline_schedule.json",
        ),
        LedgerService.from_db_path(tmp_path / "moneybot.sqlite3"),
    )


def test_explicit_deadline_parsing_succeeds(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    result = plugin.schedule(
        DeadlineScheduleRequest(
            reference_id="opp_001",
            deadline_text="2026-01-03T12:00:00+00:00",
            current_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    assert result.state.value == "upcoming"
    assert result.deadline_at is not None


def test_ambiguous_deadline_becomes_uncertain(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)

    result = plugin.schedule(
        DeadlineScheduleRequest(
            reference_id="opp_001",
            deadline_text="soon",
            current_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    assert result.state.value == "uncertain"


def test_overdue_item_detection_works(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    plugin.schedule(
        DeadlineScheduleRequest(
            reference_id="opp_001",
            deadline_text="2026-01-01",
            current_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    summary = plugin.summarize(DeadlineQueryRequest(current_time=datetime(2026, 1, 2, tzinfo=UTC)))

    assert summary.overdue_reference_ids == ["opp_001"]


def test_cooldown_window_tracking_works(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    plugin.schedule(
        DeadlineScheduleRequest(
            reference_id="opp_001",
            deadline_text="2026-01-03",
            current_time=datetime(2026, 1, 1, tzinfo=UTC),
            cooldown_until=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )

    summary = plugin.summarize(
        DeadlineQueryRequest(current_time=datetime(2026, 1, 1, 12, tzinfo=UTC))
    )

    assert summary.cooling_down_reference_ids == ["opp_001"]


def test_conflicting_deadlines_are_surfaced_explicitly(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    current_time = datetime(2026, 1, 1, tzinfo=UTC)
    plugin.schedule(
        DeadlineScheduleRequest(
            reference_id="opp_001",
            deadline_text="2026-01-03",
            current_time=current_time,
        )
    )
    plugin.schedule(
        DeadlineScheduleRequest(
            reference_id="opp_001",
            deadline_at=current_time + timedelta(days=5),
            current_time=current_time,
        )
    )

    summary = plugin.summarize(DeadlineQueryRequest(current_time=current_time))

    assert "opp_001" in summary.conflicting_reference_ids
