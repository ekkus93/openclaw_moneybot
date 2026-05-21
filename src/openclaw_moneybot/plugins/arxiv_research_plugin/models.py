"""Models for bounded arXiv research."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, HttpUrl, JsonValue, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class ArxivSearchRequest(MoneyBotModel):
    """One bounded arXiv search query."""

    query: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, gt=0, le=20)
    start: int = Field(default=0, ge=0, le=1_000)
    sort_by: Literal["relevance", "lastupdateddate", "submitteddate"] | None = None
    sort_order: Literal["ascending", "descending"] | None = None

    @field_validator("sort_by", "sort_order")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return None if normalized == "" else normalized


class ArxivPaperRequest(MoneyBotModel):
    """Request for one arXiv paper lookup."""

    arxiv_id: str = Field(min_length=1, max_length=64)

    @field_validator("arxiv_id")
    @classmethod
    def normalize_arxiv_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "arxiv_id must not be empty"
            raise ValueError(msg)
        return normalized


class ArxivPaperResultItem(MoneyBotModel):
    """One normalized arXiv paper."""

    arxiv_id: str
    title: str
    summary: str
    published: str
    updated: str
    authors: list[str] = Field(default_factory=list)
    primary_category: str | None = None
    categories: list[str] = Field(default_factory=list)
    comment: str | None = None
    doi: str | None = None
    abstract_url: HttpUrl
    pdf_url: HttpUrl | None = None


class ArxivSearchResult(MoneyBotModel):
    """Normalized arXiv search response."""

    lookup_id: str
    query: str
    start: int = Field(ge=0)
    result_count: int = Field(ge=0)
    total_results: int | None = Field(default=None, ge=0)
    sort_by: str
    sort_order: str
    results: list[ArxivPaperResultItem] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord


class ArxivPaperResult(MoneyBotModel):
    """Normalized arXiv paper lookup result."""

    lookup_id: str
    arxiv_id: str
    paper: ArxivPaperResultItem
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
