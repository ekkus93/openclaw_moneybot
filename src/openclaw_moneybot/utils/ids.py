"""Identifier helpers."""

from __future__ import annotations

from uuid import uuid4


def make_id(prefix: str) -> str:
    """Create a stable-looking prefixed identifier."""
    normalized_prefix = prefix.strip().lower().replace(" ", "_")
    return f"{normalized_prefix}_{uuid4().hex[:12]}"
