from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from skills.receipt_and_evidence_archiver.hashing import sha256_of_bytes


def ensure_archive_dir(base_path: str) -> str:
    os.makedirs(base_path, exist_ok=True)
    return base_path


def create_archive_file(
    base_path: str,
    evidence_id: str,
    related_id: str,
    content: bytes,
) -> tuple[str, str]:
    now = datetime.now(UTC)
    year = str(now.year)
    month = str(now.month).zfill(2)
    day = str(now.day).zfill(2)
    date_dir = os.path.join(base_path, year, month, day)
    os.makedirs(date_dir, exist_ok=True)
    opp_dir = os.path.join(date_dir, related_id or "unknown")
    os.makedirs(opp_dir, exist_ok=True)
    file_path = os.path.join(opp_dir, evidence_id)
    meta_path = file_path + ".metadata.json"
    with open(file_path, "wb") as f:
        f.write(content)
    sha = sha256_of_bytes(content)
    meta = {
        "evidence_id": evidence_id,
        "related_id": related_id,
        "sha256": sha,
        "size": len(content),
        "created_at": now.isoformat(),
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    return file_path, meta_path
