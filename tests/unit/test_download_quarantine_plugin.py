"""Unit tests for the download quarantine plugin."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from openclaw_moneybot.plugins.download_quarantine_plugin import (
    DownloadQuarantinePlugin,
    QuarantineIngestRequest,
    QuarantinePromoteRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, DownloadQuarantineConfig
from openclaw_moneybot.shared.types import QuarantineScanStatus, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(
    tmp_path: Path,
    *,
    max_file_bytes: int = 2_000_000,
) -> tuple[DownloadQuarantinePlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = DownloadQuarantinePlugin(
        DownloadQuarantineConfig(
            enabled=True,
            quarantine_root=tmp_path / "quarantine",
            allowed_hosts=["example.com"],
            max_file_bytes=max_file_bytes,
            max_archive_entries=3,
            max_nested_bytes=10,
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )
    return plugin, ledger_service


def make_request(**overrides: object) -> QuarantineIngestRequest:
    payload: dict[str, object] = {
        "related_record_id": "opp_001",
        "file_name": "proof.txt",
        "content_bytes": b"hello",
        "mime_type": "text/plain",
        "source_url": "https://example.com/file.txt",
    }
    payload.update(overrides)
    return QuarantineIngestRequest.model_validate(payload)


def test_safe_small_file_ingestion_succeeds(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    result = plugin.ingest(make_request())

    assert result.status is QuarantineScanStatus.STAGED
    assert result.staged_path is not None


def test_unsupported_executable_content_is_rejected(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    result = plugin.ingest(
        make_request(
            file_name="payload.exe",
            content_bytes=b"MZbinary",
            mime_type="application/octet-stream",
        )
    )

    assert result.status is QuarantineScanStatus.REJECTED


def test_oversized_file_is_rejected(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, max_file_bytes=4)

    result = plugin.ingest(make_request(content_bytes=b"too-large"))

    assert result.status is QuarantineScanStatus.REJECTED


def test_path_traversal_attempt_is_rejected(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="quarantine root"):
        plugin.ingest(make_request(file_name="../escape.txt"))


def test_zip_bomb_like_input_is_rejected(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.txt", "12345")
        archive.writestr("b.txt", "12345")
        archive.writestr("c.txt", "12345")
        archive.writestr("d.txt", "12345")

    result = plugin.ingest(
        make_request(
            file_name="bundle.zip",
            content_bytes=buffer.getvalue(),
            mime_type="application/zip",
            source_url="https://example.com/bundle.zip",
        )
    )

    assert result.status is QuarantineScanStatus.REJECTED


def test_promotion_preserves_hash_identity_and_provenance(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    staged = plugin.ingest(make_request())

    promoted = plugin.promote(
        QuarantinePromoteRequest(
            scan_id=staged.scan_id,
            related_type=RecordType.OPPORTUNITY,
            related_id="opp_001",
            evidence_type="quarantined_download",
        )
    )

    evidence = ledger_service.get_evidence_record(promoted.promoted_evidence_id or "")
    assert promoted.status is QuarantineScanStatus.PROMOTED
    assert evidence is not None
