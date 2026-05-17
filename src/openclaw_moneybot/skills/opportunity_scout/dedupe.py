"""Deduplication helpers for scout candidates."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from openclaw_moneybot.skills.opportunity_scout.models import OpportunityCandidate


def canonicalize_url(value: str) -> str:
    """Normalize URLs for duplicate detection."""
    split = urlsplit(value)
    normalized_path = split.path.rstrip("/") or "/"
    return urlunsplit((split.scheme, split.netloc.lower(), normalized_path, "", ""))


def normalize_title(value: str) -> str:
    """Normalize titles for fuzzy duplicate detection."""
    return " ".join(value.lower().split())


def dedupe_candidates(candidates: list[OpportunityCandidate]) -> list[OpportunityCandidate]:
    """Keep the highest-scoring candidate for each duplicate cluster."""
    best_by_key: dict[tuple[str, str], OpportunityCandidate] = {}
    for candidate in candidates:
        key = (canonicalize_url(str(candidate.source_url)), normalize_title(candidate.name))
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = candidate
            continue
        if candidate.score_breakdown.get("total", 0.0) > existing.score_breakdown.get("total", 0.0):
            best_by_key[key] = candidate
    return list(best_by_key.values())
