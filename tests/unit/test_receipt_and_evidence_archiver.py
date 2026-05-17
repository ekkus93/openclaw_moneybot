"""Tests for the evidence archiver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.receipt_and_evidence_archiver.hashing import verify_file_hash
from openclaw_moneybot.skills.receipt_and_evidence_archiver.storage import store_artifact


@pytest.fixture()
def archive_env(tmp_path: Path) -> tuple[ArchiveConfig, LedgerService]:
    config = ArchiveConfig(base_directory=tmp_path / "archive", redact_secrets=True)
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    return config, ledger_service


def test_text_evidence_archival(archive_env: tuple[ArchiveConfig, LedgerService]) -> None:
    config, ledger_service = archive_env
    archiver = ReceiptAndEvidenceArchiver(config, ledger_service)

    result = archiver.archive(
        EvidenceArchiveRequest(
            related_type=RecordType.OPPORTUNITY,
            related_id="opp_001",
            evidence_type="terms_page",
            content_text="Rules summary",
            source_url="https://example.com/rules",
            captured_at="2026-01-01T12:00:00Z",
        )
    )

    assert result.archive_path.exists()
    assert result.metadata_path.exists()
    assert result.ledger_record.related_record_id == "opp_001"


def test_file_evidence_archival(
    archive_env: tuple[ArchiveConfig, LedgerService], tmp_path: Path
) -> None:
    config, ledger_service = archive_env
    archiver = ReceiptAndEvidenceArchiver(config, ledger_service)
    source_path = tmp_path / "receipt.json"
    source_path.write_text('{"order":"123"}', encoding="utf-8")

    result = archiver.archive(
        EvidenceArchiveRequest(
            related_type=RecordType.SPEND_REQUEST,
            related_id="spend_001",
            evidence_type="receipt",
            content_bytes_path=source_path,
            mime_type="application/json",
            captured_at="2026-01-02T12:00:00Z",
        )
    )

    assert result.archive_path.read_text(encoding="utf-8") == '{"order":"123"}'
    assert verify_file_hash(result.archive_path, result.content_sha256) is True


def test_immutable_no_overwrite_behavior(
    archive_env: tuple[ArchiveConfig, LedgerService],
) -> None:
    config, _ledger_service = archive_env
    request = EvidenceArchiveRequest(
        related_type=RecordType.OPPORTUNITY,
        related_id="opp_001",
        evidence_type="summary",
        content_text="hello",
        captured_at="2026-01-03T12:00:00Z",
    )

    store_artifact(
        config,
        request,
        evidence_id="artifact_fixed",
        captured_at="2026-01-03T12:00:00Z",
    )
    with pytest.raises(FileExistsError):
        store_artifact(
            config,
            request,
            evidence_id="artifact_fixed",
            captured_at="2026-01-03T12:00:00Z",
        )


def test_metadata_correctness(archive_env: tuple[ArchiveConfig, LedgerService]) -> None:
    config, ledger_service = archive_env
    archiver = ReceiptAndEvidenceArchiver(config, ledger_service)

    result = archiver.archive(
        EvidenceArchiveRequest(
            related_type=RecordType.POLICY_DECISION,
            related_id="policy_001",
            evidence_type="policy_snapshot",
            content_text="allow",
            page_title="Policy snapshot",
            captured_at="2026-01-04T12:00:00Z",
        )
    )

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["page_title"] == "Policy snapshot"
    assert metadata["related_id"] == "policy_001"


def test_unsafe_path_rejection() -> None:
    with pytest.raises(ValueError):
        EvidenceArchiveRequest(
            related_type=RecordType.EVIDENCE,
            related_id="artifact_001",
            evidence_type="snapshot",
            content_bytes_path=Path("../escape.txt"),
        )


def test_secret_redaction(archive_env: tuple[ArchiveConfig, LedgerService]) -> None:
    config, ledger_service = archive_env
    archiver = ReceiptAndEvidenceArchiver(config, ledger_service)

    result = archiver.archive(
        EvidenceArchiveRequest(
            related_type=RecordType.EMAIL_DRAFT,
            related_id="email_001",
            evidence_type="email",
            content_text="wallet passphrase: hunter2\nsession cookie: abc123",
            captured_at="2026-01-05T12:00:00Z",
        )
    )

    content = result.archive_path.read_text(encoding="utf-8")
    assert "hunter2" not in content
    assert "abc123" not in content
    assert "wallet_passphrase" in result.redactions
    assert "session_cookie" in result.redactions


def test_ledger_ready_output(archive_env: tuple[ArchiveConfig, LedgerService]) -> None:
    config, ledger_service = archive_env
    archiver = ReceiptAndEvidenceArchiver(config, ledger_service)

    result = archiver.archive(
        EvidenceArchiveRequest(
            related_type=RecordType.BUDGET_PLAN,
            related_id="budget_001",
            evidence_type="budget_snapshot",
            content_text="budget details",
            captured_at="2026-01-06T12:00:00Z",
        )
    )

    timeline = ledger_service.get_opportunity_timeline("budget_001")
    assert result.ledger_record.evidence_id.startswith("artifact_")
    assert timeline == []
