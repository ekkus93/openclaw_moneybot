"""Models for bounded OpenAlex research."""

from __future__ import annotations

from pydantic import Field, HttpUrl, JsonValue, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class OpenAlexSearchRequest(MoneyBotModel):
    """One bounded OpenAlex works search query."""

    query: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, gt=0, le=20)
    page: int = Field(default=1, ge=1, le=100)
    publication_year: int | None = Field(default=None, ge=1900, le=2100)
    open_access_only: bool = False


class OpenAlexWorkRequest(MoneyBotModel):
    """Request for one OpenAlex work lookup."""

    work_id: str = Field(min_length=1, max_length=256)

    @field_validator("work_id")
    @classmethod
    def normalize_work_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "work_id must not be empty"
            raise ValueError(msg)
        return normalized


class OpenAlexWorkResultItem(MoneyBotModel):
    """One normalized OpenAlex work."""

    work_id: HttpUrl
    title: str
    doi: HttpUrl | None = None
    publication_year: int | None = Field(default=None, ge=0)
    publication_date: str | None = None
    work_type: str | None = None
    language: str | None = None
    cited_by_count: int = Field(default=0, ge=0)
    is_open_access: bool | None = None
    oa_status: str | None = None
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    primary_topic: str | None = None
    topics: list[str] = Field(default_factory=list)
    source_display_name: str | None = None
    landing_page_url: HttpUrl | None = None
    pdf_url: HttpUrl | None = None


class OpenAlexSearchResult(MoneyBotModel):
    """Normalized OpenAlex works search response."""

    lookup_id: str
    query: str
    page: int = Field(ge=1)
    result_count: int = Field(ge=0)
    total_results: int | None = Field(default=None, ge=0)
    publication_year: int | None = Field(default=None, ge=1900, le=2100)
    open_access_only: bool
    results: list[OpenAlexWorkResultItem] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord


class OpenAlexWorkResult(MoneyBotModel):
    """Normalized OpenAlex work lookup result."""

    lookup_id: str
    work_id: str
    work: OpenAlexWorkResultItem
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
