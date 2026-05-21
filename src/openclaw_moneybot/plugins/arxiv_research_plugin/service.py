"""Read-only arXiv research integration."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from openclaw_moneybot.plugins.arxiv_research_plugin.models import (
    ArxivPaperRequest,
    ArxivPaperResult,
    ArxivPaperResultItem,
    ArxivSearchRequest,
    ArxivSearchResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, ArxivResearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"
_OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"
_NS = {"atom": _ATOM_NS, "arxiv": _ARXIV_NS, "opensearch": _OPENSEARCH_NS}


class ArxivResearchPluginError(RuntimeError):
    """Raised when arXiv research cannot be completed safely."""


class ArxivResearchPlugin:
    """Search and fetch arXiv papers through the bounded read-only API."""

    def __init__(
        self,
        config: ArxivResearchConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
        self.ledger_service = ledger_service
        self._client = httpx.Client(timeout=config.timeout_seconds, transport=transport)

    def close(self) -> None:
        self._client.close()

    def health(self) -> PluginHealthResult:
        """Return plugin health metadata."""

        return PluginHealthResult(
            plugin_name="arxiv_research_plugin",
            enabled=self.config.enabled,
            read_only=True,
        )

    def search(self, request: ArxivSearchRequest) -> ArxivSearchResult:
        """Execute one bounded arXiv search query."""

        if not self.config.enabled:
            msg = "arxiv_research_plugin is disabled."
            raise ValueError(msg)
        if request.count > self.config.max_results:
            msg = "Requested result count exceeds the configured maximum."
            raise ValueError(msg)
        lookup_id = make_id("arxiv")
        sort_by = request.sort_by or self.config.default_sort_by
        sort_order = request.sort_order or self.config.default_sort_order
        try:
            response = self._client.get(
                self.config.api_base_url,
                params={
                    "search_query": self._search_query(request.query),
                    "start": request.start,
                    "max_results": request.count,
                    "sortBy": self._api_sort_by(sort_by),
                    "sortOrder": sort_order,
                },
                headers={"Accept": "application/atom+xml, application/xml"},
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(lookup_id, "arxiv_search_failed", query=request.query)
            msg = "arXiv search is unavailable."
            raise ArxivResearchPluginError(msg) from error
        except httpx.HTTPStatusError as error:
            self._record_failure(lookup_id, "arxiv_search_failed", query=request.query)
            msg = f"arXiv search request failed: {error}"
            raise ArxivResearchPluginError(msg) from error

        try:
            entries, total_results = self._parse_feed(response.text)
        except ArxivResearchPluginError:
            self._record_failure(lookup_id, "arxiv_search_failed", query=request.query)
            raise
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.ARXIV_RESEARCH,
            related_id=lookup_id,
            evidence_type="arxiv_search_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response_xml": response.text,
            },
            notes="Bounded arXiv search response snapshot",
        )
        summary = {
            "query": request.query,
            "start": request.start,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "result_ids": [item.arxiv_id for item in entries],
            "result_titles": [item.title for item in entries],
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.ARXIV_RESEARCH,
            related_record_id=lookup_id,
            payload={
                "mode": "search",
                "query": request.query,
                "start": request.start,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "result_count": len(entries),
                "total_results": total_results,
                "result_ids": [item.arxiv_id for item in entries],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return ArxivSearchResult(
            lookup_id=lookup_id,
            query=request.query,
            start=request.start,
            result_count=len(entries),
            total_results=total_results,
            sort_by=sort_by,
            sort_order=sort_order,
            results=entries,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def get_paper(self, request: ArxivPaperRequest) -> ArxivPaperResult:
        """Fetch one bounded arXiv paper entry by arXiv ID."""

        if not self.config.enabled:
            msg = "arxiv_research_plugin is disabled."
            raise ValueError(msg)
        lookup_id = make_id("arxiv")
        try:
            response = self._client.get(
                self.config.api_base_url,
                params={
                    "id_list": request.arxiv_id,
                    "max_results": 1,
                },
                headers={"Accept": "application/atom+xml, application/xml"},
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(lookup_id, "arxiv_paper_lookup_failed", arxiv_id=request.arxiv_id)
            msg = "arXiv paper lookup is unavailable."
            raise ArxivResearchPluginError(msg) from error
        except httpx.HTTPStatusError as error:
            self._record_failure(lookup_id, "arxiv_paper_lookup_failed", arxiv_id=request.arxiv_id)
            msg = f"arXiv paper lookup request failed: {error}"
            raise ArxivResearchPluginError(msg) from error

        try:
            entries, _ = self._parse_feed(response.text)
        except ArxivResearchPluginError:
            self._record_failure(lookup_id, "arxiv_paper_lookup_failed", arxiv_id=request.arxiv_id)
            raise
        if not entries:
            self._record_failure(lookup_id, "arxiv_paper_not_found", arxiv_id=request.arxiv_id)
            msg = "arXiv paper lookup returned no matching paper."
            raise ArxivResearchPluginError(msg)
        paper = entries[0]
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.ARXIV_RESEARCH,
            related_id=lookup_id,
            evidence_type="arxiv_paper_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response_xml": response.text,
            },
            notes="Bounded arXiv paper lookup response snapshot",
        )
        summary = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "primary_category": paper.primary_category,
            "pdf_url": str(paper.pdf_url) if paper.pdf_url is not None else None,
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.ARXIV_RESEARCH,
            related_record_id=lookup_id,
            payload={
                "mode": "paper_lookup",
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "primary_category": paper.primary_category,
                "evidence_archive_ids": [evidence_id],
            },
        )
        return ArxivPaperResult(
            lookup_id=lookup_id,
            arxiv_id=paper.arxiv_id,
            paper=paper,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def _record_failure(self, lookup_id: str, event_name: str, **payload: object) -> None:
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=lookup_id,
            event_name=event_name,
            payload=payload,
        )

    def _parse_feed(self, xml_text: str) -> tuple[list[ArxivPaperResultItem], int | None]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as error:
            msg = "arXiv response must be valid Atom XML."
            raise ArxivResearchPluginError(msg) from error
        if root.tag != f"{{{_ATOM_NS}}}feed":
            msg = "arXiv response root must be an Atom feed."
            raise ArxivResearchPluginError(msg)
        total_results_text = root.findtext("opensearch:totalResults", namespaces=_NS)
        total_results = None
        if total_results_text and total_results_text.isdigit():
            total_results = int(total_results_text)
        entries = [
            self._parse_entry(entry)
            for entry in root.findall("atom:entry", _NS)
        ]
        return entries, total_results

    def _parse_entry(self, entry: ET.Element) -> ArxivPaperResultItem:
        title = self._required_text(entry, "atom:title", "arXiv entry title")
        summary = self._required_text(entry, "atom:summary", "arXiv entry summary")
        published = self._required_text(entry, "atom:published", "arXiv entry published date")
        updated = self._required_text(entry, "atom:updated", "arXiv entry updated date")
        abstract_url = self._required_text(entry, "atom:id", "arXiv entry id")
        arxiv_id = self._extract_arxiv_id(abstract_url)
        authors = [
            name
            for name in (
                self._clean_text(author.findtext("atom:name", default="", namespaces=_NS))
                for author in entry.findall("atom:author", _NS)
            )
            if name
        ]
        primary_category_element = entry.find("arxiv:primary_category", _NS)
        primary_category = None
        if primary_category_element is not None:
            primary_category = self._clean_text(primary_category_element.attrib.get("term", ""))
        categories = [
            category
            for category in (
                self._clean_text(category_element.attrib.get("term", ""))
                for category_element in entry.findall("atom:category", _NS)
            )
            if category
        ]
        comment = self._optional_text(entry, "arxiv:comment")
        doi = self._optional_text(entry, "arxiv:doi")
        pdf_url = self._extract_pdf_url(entry)
        return ArxivPaperResultItem(
            arxiv_id=arxiv_id,
            title=title,
            summary=summary[: self.config.max_summary_chars],
            published=published,
            updated=updated,
            authors=authors,
            primary_category=primary_category,
            categories=categories,
            comment=comment,
            doi=doi,
            abstract_url=abstract_url,
            pdf_url=pdf_url,
        )

    @staticmethod
    def _required_text(entry: ET.Element, path: str, description: str) -> str:
        text = entry.findtext(path, default="", namespaces=_NS)
        normalized = ArxivResearchPlugin._clean_text(text)
        if not normalized:
            msg = f"arXiv response missing {description}."
            raise ArxivResearchPluginError(msg)
        return normalized

    @staticmethod
    def _optional_text(entry: ET.Element, path: str) -> str | None:
        text = entry.findtext(path, default="", namespaces=_NS)
        normalized = ArxivResearchPlugin._clean_text(text)
        return normalized or None

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _extract_arxiv_id(abstract_url: str) -> str:
        marker = "/abs/"
        if marker not in abstract_url:
            msg = "arXiv entry id must point to an abstract URL."
            raise ArxivResearchPluginError(msg)
        return abstract_url.split(marker, 1)[1]

    @staticmethod
    def _extract_pdf_url(entry: ET.Element) -> str | None:
        for link in entry.findall("atom:link", _NS):
            href = link.attrib.get("href", "").strip()
            if not href:
                continue
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                return href
        return None

    @staticmethod
    def _search_query(query: str) -> str:
        normalized = " ".join(query.replace('"', " ").split())
        return f'all:"{normalized}"'

    @staticmethod
    def _api_sort_by(value: str) -> str:
        if value == "lastupdateddate":
            return "lastUpdatedDate"
        if value == "submitteddate":
            return "submittedDate"
        return "relevance"
