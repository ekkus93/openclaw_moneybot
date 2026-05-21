"""Models for bounded Brave Search requests."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, HttpUrl, JsonValue, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class BraveSearchRequest(MoneyBotModel):
    """One bounded Brave Search query."""

    query: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, gt=0, le=20)
    country: str | None = None
    search_lang: str | None = None
    safesearch: str | None = None
    freshness: str | None = None

    @field_validator("country", "search_lang", "safesearch", "freshness")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return None if normalized == "" else normalized


class BraveNewsSearchRequest(MoneyBotModel):
    """One bounded current-events/news query using Brave web search."""

    query: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, gt=0, le=20)
    freshness: str | None = None
    source_domains: list[str] = Field(default_factory=list, max_length=8)
    country: str | None = None
    search_lang: str | None = None
    safesearch: str | None = None

    @field_validator("freshness", "country", "search_lang", "safesearch")
    @classmethod
    def normalize_optional_news_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return None if normalized == "" else normalized

    @field_validator("source_domains")
    @classmethod
    def normalize_source_domains(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for domain in value:
            stripped = domain.strip().lower()
            if stripped:
                normalized.append(stripped)
        return normalized


class BraveSearchResultItem(MoneyBotModel):
    """One normalized Brave Search web result."""

    title: str
    url: HttpUrl
    description: str = ""
    age: str | None = None
    language: str | None = None
    family_friendly: bool | None = None


class BraveSearchResult(MoneyBotModel):
    """Normalized Brave Search query result."""

    search_id: str
    query: str
    results: list[BraveSearchResultItem] = Field(default_factory=list)
    mode: Literal["web", "news"] = "web"
    provider: str = "brave_search"
    result_count: int = Field(ge=0)
    freshness: str | None = None
    source_domains: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
