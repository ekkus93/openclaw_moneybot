"""Models for bounded Wikipedia research."""

from __future__ import annotations

from pydantic import Field, HttpUrl, JsonValue, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class WikipediaSearchRequest(MoneyBotModel):
    """One bounded Wikipedia search query."""

    query: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, gt=0, le=20)
    language: str | None = None

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return None if normalized == "" else normalized


class WikipediaPageRequest(MoneyBotModel):
    """Request for one Wikipedia page summary."""

    title: str = Field(min_length=1, max_length=300)
    language: str | None = None
    max_extract_chars: int | None = Field(default=None, gt=0, le=10_000)

    @field_validator("language")
    @classmethod
    def normalize_page_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return None if normalized == "" else normalized


class WikipediaSearchResultItem(MoneyBotModel):
    """One normalized Wikipedia search result."""

    title: str
    page_id: int = Field(ge=0)
    url: HttpUrl
    snippet: str = ""


class WikipediaSearchResult(MoneyBotModel):
    """Normalized Wikipedia search response."""

    lookup_id: str
    query: str
    language: str
    results: list[WikipediaSearchResultItem] = Field(default_factory=list)
    result_count: int = Field(ge=0)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord


class WikipediaPageResult(MoneyBotModel):
    """Normalized Wikipedia page summary."""

    lookup_id: str
    title: str
    canonical_url: HttpUrl
    language: str
    summary: str
    page_id: int | None = Field(default=None, ge=0)
    revision: int | None = Field(default=None, ge=0)
    last_modified: str | None = None
    content_urls: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
