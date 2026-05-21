"""Models for bounded biomedical research."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, HttpUrl, JsonValue

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord

BiomedicalProvider = Literal["pubmed", "europe_pmc"]


class BiomedicalSearchRequest(MoneyBotModel):
    """One bounded biomedical paper search query."""

    provider: BiomedicalProvider
    query: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, gt=0, le=20)
    page: int = Field(default=1, ge=1, le=100)
    publication_year: int | None = Field(default=None, ge=1900, le=2100)


class BiomedicalPaperRequest(MoneyBotModel):
    """Request for one biomedical paper lookup."""

    provider: BiomedicalProvider
    paper_id: str = Field(min_length=1, max_length=128)


class BiomedicalPaperResultItem(MoneyBotModel):
    """One normalized biomedical paper."""

    provider: BiomedicalProvider
    paper_id: str
    title: str
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    publication_year: int | None = Field(default=None, ge=0)
    publication_date: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    cited_by_count: int | None = Field(default=None, ge=0)
    is_open_access: bool | None = None
    source_url: HttpUrl | None = None


class BiomedicalSearchResult(MoneyBotModel):
    """Normalized biomedical search response."""

    lookup_id: str
    provider: BiomedicalProvider
    query: str
    page: int = Field(ge=1)
    result_count: int = Field(ge=0)
    total_results: int | None = Field(default=None, ge=0)
    publication_year: int | None = Field(default=None, ge=1900, le=2100)
    results: list[BiomedicalPaperResultItem] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord


class BiomedicalPaperResult(MoneyBotModel):
    """Normalized biomedical paper lookup result."""

    lookup_id: str
    provider: BiomedicalProvider
    paper_id: str
    paper: BiomedicalPaperResultItem
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
