"""Hashing helpers for evidence archival."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(content: bytes) -> str:
    """Hash bytes with SHA-256."""
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file with SHA-256."""
    return sha256_bytes(path.read_bytes())


def verify_file_hash(path: Path, expected_hash: str) -> bool:
    """Verify a file hash matches the expected SHA-256."""
    return sha256_file(path) == expected_hash
