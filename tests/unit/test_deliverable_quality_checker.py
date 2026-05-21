"""Unit tests for deliverable quality checks."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import DeliverableValidationOutcome
from openclaw_moneybot.skills.deliverable_quality_checker import (
    DeliverableArtifact,
    DeliverableQualityChecker,
    DeliverableQualityCheckRequest,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_checker(tmp_path: Path) -> DeliverableQualityChecker:
    return DeliverableQualityChecker(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        LedgerService.from_db_path(tmp_path / "moneybot.sqlite3"),
    )


def make_request(**overrides: object) -> DeliverableQualityCheckRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "submission_package_id": "submission_package_001",
        "required_fields": ["name"],
        "required_artifacts": ["screenshot"],
        "field_values": {"name": "Valid name"},
        "artifacts": [
            DeliverableArtifact(
                artifact_name="screenshot",
                content_text="real screenshot evidence",
                evidence_archive_id="artifact_001",
            )
        ],
    }
    payload.update(overrides)
    return DeliverableQualityCheckRequest.model_validate(payload)


def test_complete_package_passes(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(make_request())

    assert result.status is DeliverableValidationOutcome.PASSED


def test_missing_screenshot_fails(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(make_request(artifacts=[]))

    assert result.status is DeliverableValidationOutcome.FAILED
    assert "artifact:screenshot" in result.missing_items


def test_placeholder_content_fails(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            artifacts=[
                DeliverableArtifact(
                    artifact_name="screenshot",
                    content_text="TODO",
                )
            ]
        )
    )

    assert result.status is DeliverableValidationOutcome.FAILED


def test_hash_mismatch_fails(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            artifacts=[
                DeliverableArtifact(
                    artifact_name="screenshot",
                    content_text="real",
                    expected_sha256="abc",
                    actual_sha256="def",
                )
            ]
        )
    )

    assert result.status is DeliverableValidationOutcome.FAILED


def test_optional_warning_does_not_become_false_success(tmp_path: Path) -> None:
    result = make_checker(tmp_path).evaluate(
        make_request(
            artifacts=[DeliverableArtifact(artifact_name="screenshot", content_text="real")]
        )
    )

    assert result.status is DeliverableValidationOutcome.NEEDS_REVIEW
