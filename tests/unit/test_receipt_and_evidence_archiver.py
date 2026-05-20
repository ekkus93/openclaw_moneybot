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
    config = ArchiveConfig(
        base_directory=tmp_path / "archive",
        redact_secrets=True,
        allowed_source_roots=[tmp_path],
        max_artifact_bytes=128,
    )
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


def test_unsafe_path_rejection(archive_env: tuple[ArchiveConfig, LedgerService]) -> None:
    config, _ledger_service = archive_env
    request = EvidenceArchiveRequest(
        related_type=RecordType.EVIDENCE,
        related_id="artifact_001",
        evidence_type="snapshot",
        content_bytes_path=Path("/etc/passwd"),
    )

    with pytest.raises(ValueError):
        store_artifact(
            config,
            request,
            evidence_id="artifact_outside_root",
            captured_at="2026-01-04T12:00:00Z",
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


def test_symlink_escape_rejection(
    archive_env: tuple[ArchiveConfig, LedgerService],
    tmp_path: Path,
) -> None:
    config, _ledger_service = archive_env
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_text("escape", encoding="utf-8")
    symlink_path = tmp_path / "outside-link.txt"
    symlink_path.symlink_to(outside_file)

    request = EvidenceArchiveRequest(
        related_type=RecordType.EVIDENCE,
        related_id="artifact_001",
        evidence_type="snapshot",
        content_bytes_path=symlink_path,
    )

    with pytest.raises(ValueError):
        store_artifact(
            config,
            request,
            evidence_id="artifact_symlink",
            captured_at="2026-01-07T12:00:00Z",
        )


def test_directory_rejection(
    archive_env: tuple[ArchiveConfig, LedgerService],
    tmp_path: Path,
) -> None:
    config, _ledger_service = archive_env
    source_dir = tmp_path / "directory"
    source_dir.mkdir()
    request = EvidenceArchiveRequest(
        related_type=RecordType.EVIDENCE,
        related_id="artifact_001",
        evidence_type="snapshot",
        content_bytes_path=source_dir,
    )

    with pytest.raises(ValueError):
        store_artifact(
            config,
            request,
            evidence_id="artifact_directory",
            captured_at="2026-01-08T12:00:00Z",
        )


def test_max_file_size_rejection(
    archive_env: tuple[ArchiveConfig, LedgerService],
    tmp_path: Path,
) -> None:
    config, _ledger_service = archive_env
    source_path = tmp_path / "oversized.txt"
    source_path.write_text("x" * 129, encoding="utf-8")
    request = EvidenceArchiveRequest(
        related_type=RecordType.EVIDENCE,
        related_id="artifact_001",
        evidence_type="snapshot",
        content_bytes_path=source_path,
    )

    with pytest.raises(ValueError):
        store_artifact(
            config,
            request,
            evidence_id="artifact_oversized",
            captured_at="2026-01-09T12:00:00Z",
        )


def test_max_content_text_size_rejection(
    archive_env: tuple[ArchiveConfig, LedgerService],
) -> None:
    config, ledger_service = archive_env
    archiver = ReceiptAndEvidenceArchiver(config, ledger_service)

    with pytest.raises(ValueError, match="max_artifact_bytes"):
        archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id="opp_001",
                evidence_type="summary",
                content_text="x" * 129,
                captured_at="2026-01-10T12:00:00Z",
            )
        )

    assert not any(config.base_directory.rglob("*"))
    assert ledger_service.list_evidence_for_related(
        related_type=RecordType.OPPORTUNITY,
        related_id="opp_001",
    ) == []


def test_boundary_content_text_size_is_accepted(
    archive_env: tuple[ArchiveConfig, LedgerService],
) -> None:
    config, ledger_service = archive_env
    archiver = ReceiptAndEvidenceArchiver(config, ledger_service)

    result = archiver.archive(
        EvidenceArchiveRequest(
            related_type=RecordType.OPPORTUNITY,
            related_id="opp_001",
            evidence_type="summary",
            content_text="x" * 128,
            captured_at="2026-01-11T12:00:00Z",
        )
    )

    assert result.file_size == 128
    assert result.archive_path.exists()


@pytest.mark.parametrize(
    "evidence_type",
    ["../../evil", "foo/bar", r"foo\\bar", "bad\x00type", "", "a" * 65, "receipt;rm"],
)
def test_unsafe_evidence_type_rejected_without_side_effects(
    archive_env: tuple[ArchiveConfig, LedgerService],
    evidence_type: str,
) -> None:
    config, ledger_service = archive_env
    archiver = ReceiptAndEvidenceArchiver(config, ledger_service)

    with pytest.raises(ValueError):
        archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id="opp_001",
                evidence_type=evidence_type,
                content_text="hello",
                captured_at="2026-01-12T12:00:00Z",
            )
        )

    assert not any(config.base_directory.rglob("*"))
    assert ledger_service.list_evidence_for_related(
        related_type=RecordType.OPPORTUNITY,
        related_id="opp_001",
    ) == []
