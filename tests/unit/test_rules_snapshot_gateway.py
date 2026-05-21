"""Unit tests for rules snapshot capture."""

from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_moneybot.plugins.rules_snapshot_gateway import (
    RulesSnapshotCaptureRequest,
    RulesSnapshotGateway,
)
from openclaw_moneybot.shared import ArchiveConfig, RulesSnapshotGatewayConfig
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_gateway(tmp_path: Path) -> RulesSnapshotGateway:
    return RulesSnapshotGateway(
        RulesSnapshotGatewayConfig(enabled=True, allowed_hosts=["example.com"]),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        LedgerService.from_db_path(tmp_path / "moneybot.sqlite3"),
    )


def make_request(**overrides: object) -> RulesSnapshotCaptureRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "source_url": "https://example.com/rules",
        "content_text": "Line one\nLine two\n",
        "content_type": "text/plain",
        "idempotency_key": "rules:1",
    }
    payload.update(overrides)
    return RulesSnapshotCaptureRequest.model_validate(payload)


def test_initial_snapshot_capture_succeeds(tmp_path: Path) -> None:
    result = make_gateway(tmp_path).capture(make_request())

    assert result.normalized_hash
    assert len(result.evidence_archive_ids) >= 2


def test_same_content_recapture_yields_same_hash_identity_expectations(tmp_path: Path) -> None:
    gateway = make_gateway(tmp_path)
    first = gateway.capture(make_request(idempotency_key="rules:first"))
    second = gateway.capture(make_request(idempotency_key="rules:second"))

    assert second.normalized_hash == first.normalized_hash
    assert second.change_detected is False
    assert second.previous_snapshot_record_id is not None


def test_meaningful_text_changes_appear_in_diff_output(tmp_path: Path) -> None:
    gateway = make_gateway(tmp_path)
    gateway.capture(make_request(idempotency_key="rules:first"))

    result = gateway.capture(
        make_request(
            content_text="Line one\nChanged line\n",
            idempotency_key="rules:changed",
        )
    )

    assert result.change_detected is True
    assert "Changed line" in result.diff_text


def test_unsupported_content_type_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="content type"):
        make_gateway(tmp_path).capture(make_request(content_type="application/pdf"))


def test_oversized_content_is_rejected(tmp_path: Path) -> None:
    gateway = RulesSnapshotGateway(
        RulesSnapshotGatewayConfig(
            enabled=True,
            allowed_hosts=["example.com"],
            max_content_bytes=4,
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        LedgerService.from_db_path(tmp_path / "moneybot.sqlite3"),
    )

    with pytest.raises(ValueError, match="size limit"):
        gateway.capture(make_request(content_text="too large"))


def test_non_allowlisted_host_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allowlisted"):
        make_gateway(tmp_path).capture(make_request(source_url="https://evil.example/rules"))


def test_evidence_and_ledger_linkage_are_preserved(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    gateway = RulesSnapshotGateway(
        RulesSnapshotGatewayConfig(enabled=True, allowed_hosts=["example.com"]),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )

    result = gateway.capture(make_request())

    assert ledger_service.get_related_events(related_type=result.ledger_record.record_type)
    assert result.evidence_archive_ids
