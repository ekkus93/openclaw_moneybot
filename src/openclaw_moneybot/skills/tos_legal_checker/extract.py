"""Offline evidence extraction helpers for TOS/legal review."""

from __future__ import annotations

from html import unescape
from re import sub

KEYWORDS = (
    "bot",
    "automation",
    "commercial",
    "payment",
    "eligibility",
    "spam",
    "data",
    "privacy",
    "refund",
    "submission",
    "affiliate",
)


def normalize_text(value: str) -> str:
    """Normalize raw evidence text for rule scanning."""
    stripped = sub(r"<[^>]+>", " ", value)
    collapsed = sub(r"\s+", " ", unescape(stripped)).strip()
    return collapsed


def extract_relevant_snippets(value: str, *, max_snippets: int = 5) -> list[str]:
    """Extract short snippets near keywords of interest."""
    normalized = normalize_text(value)
    sentences = [segment.strip() for segment in normalized.split(".") if segment.strip()]
    snippets: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in KEYWORDS):
            snippets.append(sentence)
        if len(snippets) >= max_snippets:
            break
    return snippets
