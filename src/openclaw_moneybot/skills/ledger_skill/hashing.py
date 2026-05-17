"""Tamper-evident ledger hashing helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialize a payload consistently for hashing and storage."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(value: str) -> str:
    """Return a SHA-256 hex digest for the given string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_event_hash(previous_event_hash: str | None, payload_json: str) -> str:
    """Compute a tamper-evident event hash."""
    previous = previous_event_hash or ""
    return sha256_hex(f"{previous}:{payload_json}")


def verify_hash_chain(
    events: list[dict[str, str | None]],
) -> bool:
    """Verify a sequence of ledger events."""
    previous: str | None = None
    for event in events:
        expected_hash = compute_event_hash(previous, str(event["payload_json"]))
        if event["previous_event_hash"] != previous:
            return False
        if event["event_hash"] != expected_hash:
            return False
        previous = str(event["event_hash"])
    return True
