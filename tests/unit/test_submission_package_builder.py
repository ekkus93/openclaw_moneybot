"""Unit tests for submission package building."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import SubmissionReadinessStatus
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.submission_package_builder import (
    SubmissionPackageBuilder,
    SubmissionPackageBuildRequest,
)


def make_builder(tmp_path: Path) -> SubmissionPackageBuilder:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    return SubmissionPackageBuilder(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )


def make_request(**overrides: object) -> SubmissionPackageBuildRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "opportunity_name": "Bounty",
        "rules_text": (
            "Required fields: name, email, repository link\n"
            "Attachments: screenshot\n"
            "Submit at https://example.com/submit\n"
            "Deadline: 2026-01-02"
        ),
        "source_url": "https://example.com/rules",
        "policy_decision_id": "policy_001",
        "tos_legal_check_id": "tos_001",
        "budget_plan_id": "budget_001",
    }
    payload.update(overrides)
    return SubmissionPackageBuildRequest.model_validate(payload)


def test_structured_rules_become_deterministic_checklist_items(tmp_path: Path) -> None:
    result = make_builder(tmp_path).build(make_request())

    assert result.status is SubmissionReadinessStatus.READY
    assert "name" in result.required_fields
    assert "screenshot" in result.required_artifacts


def test_missing_required_field_text_becomes_review_required(tmp_path: Path) -> None:
    result = make_builder(tmp_path).build(
        make_request(rules_text="Please complete the required fields before submitting.")
    )

    assert result.status is SubmissionReadinessStatus.NEEDS_REVIEW
    assert "required_fields_not_explicit" in result.unresolved_items


def test_conflicting_deliverable_instructions_fail_closed(tmp_path: Path) -> None:
    result = make_builder(tmp_path).build(
        make_request(
            rules_text=(
                "Provide 1 screenshot.\n"
                "Also provide 2 screenshots.\n"
                "Required fields: email"
            )
        )
    )

    assert result.status is SubmissionReadinessStatus.BLOCKED
    assert "conflicting_screenshot_counts" in result.unresolved_items


def test_submission_url_and_deadline_are_preserved(tmp_path: Path) -> None:
    result = make_builder(tmp_path).build(make_request())

    assert result.submission_url == "https://example.com/submit"
    assert result.deadline == "2026-01-02"
