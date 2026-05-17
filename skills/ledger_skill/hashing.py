from __future__ import annotations

import hashlib


def hash_payload(payload: str | bytes) -> str:
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(data).hexdigest()


def hash_event(
    previous_event_hash: str | None,
    payload_json: str,
) -> str:
    base = (previous_event_hash or "") + payload_json
    return hash_payload(base)
