"""Models for bounded Brave Search requests."""

from __future__ import annotations

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
    provider: str = "brave_search"
    result_count: int = Field(ge=0)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
