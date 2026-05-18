"""Local storage helpers for evidence archival."""

from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path

from openclaw_moneybot.shared.config import ArchiveConfig
from openclaw_moneybot.skills.receipt_and_evidence_archiver.hashing import sha256_bytes
from openclaw_moneybot.skills.receipt_and_evidence_archiver.models import EvidenceArchiveRequest

SECRET_PATTERNS = {
    "wallet_passphrase": re.compile(r"(wallet passphrase\s*:\s*)(.+)", re.IGNORECASE),
    "private_key": re.compile(r"(private key\s*:\s*)(.+)", re.IGNORECASE),
    "seed_phrase": re.compile(r"(seed phrase\s*:\s*)(.+)", re.IGNORECASE),
    "session_cookie": re.compile(r"(session cookie\s*:\s*)(.+)", re.IGNORECASE),
    "oauth_token": re.compile(r"(oauth token\s*:\s*)(.+)", re.IGNORECASE),
}

TEXTUAL_MIME_PREFIXES = ("text/", "application/json", "message/")
TEXTUAL_SUFFIXES = {".txt", ".json", ".html", ".md", ".eml", ".csv", ".xml"}
SENSITIVE_PATH_MARKERS = (
    "/etc/",
    "/root/",
    "/.ssh/",
    "/bitcoin/",
    "/wallet.dat",
    "/cookies",
    "/browser",
    "/secrets",
    ".env",
)


def normalize_evidence_type(value: str) -> str:
    """Normalize evidence type values."""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def detect_extension(request: EvidenceArchiveRequest) -> str:
    """Detect the best file extension for an archived artifact."""
    if request.content_bytes_path is not None and request.content_bytes_path.suffix:
        return request.content_bytes_path.suffix.lower()
    if request.mime_type is not None:
        guessed = mimetypes.guess_extension(request.mime_type)
        if guessed is not None:
            return guessed
    return ".txt"


def is_textual(request: EvidenceArchiveRequest, extension: str) -> bool:
    """Return whether content should be treated as text for redaction."""
    if request.content_text is not None:
        return True
    if request.mime_type is not None and request.mime_type.startswith(TEXTUAL_MIME_PREFIXES):
        return True
    return extension in TEXTUAL_SUFFIXES


def redact_text(content: str) -> tuple[str, list[str]]:
    """Redact sensitive values from textual evidence."""
    redactions: list[str] = []
    redacted = content
    for name, pattern in SECRET_PATTERNS.items():
        updated = pattern.sub(r"\1[REDACTED]", redacted)
        if updated != redacted:
            redactions.append(name)
            redacted = updated
    return redacted, redactions


def build_archive_paths(
    config: ArchiveConfig,
    *,
    evidence_id: str,
    related_id: str,
    captured_at: str,
    evidence_type: str,
    extension: str,
) -> tuple[Path, Path]:
    """Build immutable content and metadata paths."""
    date_prefix = captured_at[:10].replace("-", "/")
    archive_dir = config.base_directory / date_prefix / f"related_{related_id}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{captured_at.replace(':', '').replace('-', '')}_{evidence_type}_{evidence_id}"
    content_path = archive_dir / f"{base_name}{extension}"
    metadata_path = archive_dir / f"{base_name}.metadata.json"
    return content_path, metadata_path


def resolve_source_path(config: ArchiveConfig, source_path: Path) -> Path:
    """Resolve and validate a local source path against the archive allowlist."""
    resolved_source = source_path.expanduser().resolve(strict=True)
    if resolved_source.is_dir():
        msg = "Directories cannot be archived as evidence artifacts."
        raise ValueError(msg)
    if not resolved_source.is_file():
        msg = "Only regular files can be archived as evidence artifacts."
        raise ValueError(msg)
    path_string = resolved_source.as_posix().lower()
    if any(marker in path_string for marker in SENSITIVE_PATH_MARKERS):
        msg = "Sensitive paths cannot be archived as evidence artifacts."
        raise ValueError(msg)
    if not config.allowed_source_roots:
        msg = "File-based evidence archival requires an allowed_source_roots configuration."
        raise ValueError(msg)
    resolved_roots = [
        root.expanduser().resolve(strict=False)
        for root in config.allowed_source_roots
    ]
    if not any(
        root == resolved_source or root in resolved_source.parents
        for root in resolved_roots
    ):
        msg = "Evidence file source is outside the configured workspace allowlist."
        raise ValueError(msg)
    return resolved_source


def store_artifact(
    config: ArchiveConfig,
    request: EvidenceArchiveRequest,
    *,
    evidence_id: str,
    captured_at: str,
) -> tuple[Path, Path, str, int, list[str]]:
    """Store an artifact and its metadata."""
    normalized_type = normalize_evidence_type(request.evidence_type)
    extension = detect_extension(request)
    content_path, metadata_path = build_archive_paths(
        config,
        evidence_id=evidence_id,
        related_id=request.related_id,
        captured_at=captured_at,
        evidence_type=normalized_type,
        extension=extension,
    )
    if content_path.exists() or metadata_path.exists():
        msg = "Refusing to overwrite an existing archived artifact."
        raise FileExistsError(msg)

    redactions: list[str] = []
    if request.content_text is not None:
        content_text = request.content_text
        if config.redact_secrets:
            content_text, redactions = redact_text(content_text)
        content_bytes = content_text.encode("utf-8")
    else:
        assert request.content_bytes_path is not None
        resolved_source = resolve_source_path(config, request.content_bytes_path)
        if resolved_source.stat().st_size > config.max_artifact_bytes:
            msg = "Evidence artifact exceeds the configured max_artifact_bytes limit."
            raise ValueError(msg)
        content_bytes = resolved_source.read_bytes()
        if config.redact_secrets and is_textual(request, extension):
            decoded = content_bytes.decode("utf-8")
            redacted_text, redactions = redact_text(decoded)
            content_bytes = redacted_text.encode("utf-8")

    content_path.write_bytes(content_bytes)
    content_sha256 = sha256_bytes(content_bytes)
    metadata = {
        "evidence_id": evidence_id,
        "related_type": request.related_type.value,
        "related_id": request.related_id,
        "evidence_type": normalized_type,
        "source_url": None if request.source_url is None else str(request.source_url),
        "final_url": None if request.final_url is None else str(request.final_url),
        "page_title": request.page_title,
        "captured_at": captured_at,
        "mime_type": request.mime_type,
        "notes": request.notes,
        "summary_hint": request.summary_hint,
        "content_sha256": content_sha256,
        "redactions": redactions,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return content_path, metadata_path, content_sha256, len(content_bytes), redactions
