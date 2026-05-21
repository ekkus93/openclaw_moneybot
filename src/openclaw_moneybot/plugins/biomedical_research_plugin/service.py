"""Read-only PubMed and Europe PMC research integration."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from openclaw_moneybot.plugins.biomedical_research_plugin.models import (
    BiomedicalPaperRequest,
    BiomedicalPaperResult,
    BiomedicalPaperResultItem,
    BiomedicalSearchRequest,
    BiomedicalSearchResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, BiomedicalResearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class BiomedicalResearchPluginError(RuntimeError):
    """Raised when biomedical research cannot be completed safely."""


class BiomedicalResearchPlugin:
    """Search and fetch papers through bounded PubMed and Europe PMC APIs."""

    def __init__(
        self,
        config: BiomedicalResearchConfig,
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
            plugin_name="biomedical_research_plugin",
            enabled=self.config.enabled,
            read_only=True,
        )

    def search(self, request: BiomedicalSearchRequest) -> BiomedicalSearchResult:
        """Execute one bounded PubMed or Europe PMC search."""

        if not self.config.enabled:
            msg = "biomedical_research_plugin is disabled."
            raise ValueError(msg)
        if request.count > self.config.max_results:
            msg = "Requested result count exceeds the configured maximum."
            raise ValueError(msg)
        lookup_id = make_id("biomedical")
        try:
            if request.provider == "pubmed":
                results, total_results, raw_payload = self._search_pubmed(request)
            else:
                results, total_results, raw_payload = self._search_europe_pmc(request)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(
                lookup_id,
                f"{request.provider}_search_failed",
                query=request.query,
            )
            msg = f"{self._provider_label(request.provider)} search is unavailable."
            raise BiomedicalResearchPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError, BiomedicalResearchPluginError) as error:
            self._record_failure(
                lookup_id,
                f"{request.provider}_search_failed",
                query=request.query,
            )
            msg = f"{self._provider_label(request.provider)} search request failed: {error}"
            raise BiomedicalResearchPluginError(msg) from error

        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.BIOMEDICAL_RESEARCH,
            related_id=lookup_id,
            evidence_type=f"{request.provider}_search_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": raw_payload,
            },
            notes=f"Bounded {self._provider_label(request.provider)} search response snapshot",
        )
        summary = {
            "provider": request.provider,
            "query": request.query,
            "page": request.page,
            "publication_year": request.publication_year,
            "result_ids": [item.paper_id for item in results],
            "result_titles": [item.title for item in results],
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.BIOMEDICAL_RESEARCH,
            related_record_id=lookup_id,
            payload={
                "provider": request.provider,
                "mode": "search",
                "query": request.query,
                "page": request.page,
                "publication_year": request.publication_year,
                "result_count": len(results),
                "total_results": total_results,
                "result_ids": [item.paper_id for item in results],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return BiomedicalSearchResult(
            lookup_id=lookup_id,
            provider=request.provider,
            query=request.query,
            page=request.page,
            result_count=len(results),
            total_results=total_results,
            publication_year=request.publication_year,
            results=results,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def get_paper(self, request: BiomedicalPaperRequest) -> BiomedicalPaperResult:
        """Fetch one bounded PubMed or Europe PMC paper."""

        if not self.config.enabled:
            msg = "biomedical_research_plugin is disabled."
            raise ValueError(msg)
        lookup_id = make_id("biomedical")
        try:
            if request.provider == "pubmed":
                paper, raw_payload = self._get_pubmed_paper(request.paper_id)
            else:
                paper, raw_payload = self._get_europe_pmc_paper(request.paper_id)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(
                lookup_id,
                f"{request.provider}_paper_lookup_failed",
                paper_id=request.paper_id,
            )
            msg = f"{self._provider_label(request.provider)} paper lookup is unavailable."
            raise BiomedicalResearchPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError, BiomedicalResearchPluginError) as error:
            self._record_failure(
                lookup_id,
                f"{request.provider}_paper_lookup_failed",
                paper_id=request.paper_id,
            )
            msg = f"{self._provider_label(request.provider)} paper lookup request failed: {error}"
            raise BiomedicalResearchPluginError(msg) from error

        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.BIOMEDICAL_RESEARCH,
            related_id=lookup_id,
            evidence_type=f"{request.provider}_paper_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": raw_payload,
            },
            notes=(
                f"Bounded {self._provider_label(request.provider)} "
                "paper lookup response snapshot"
            ),
        )
        summary = {
            "provider": request.provider,
            "paper_id": paper.paper_id,
            "title": paper.title,
            "pmid": paper.pmid,
            "pmcid": paper.pmcid,
            "doi": paper.doi,
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.BIOMEDICAL_RESEARCH,
            related_record_id=lookup_id,
            payload={
                "provider": request.provider,
                "mode": "paper_lookup",
                "paper_id": paper.paper_id,
                "title": paper.title,
                "pmid": paper.pmid,
                "pmcid": paper.pmcid,
                "doi": paper.doi,
                "evidence_archive_ids": [evidence_id],
            },
        )
        return BiomedicalPaperResult(
            lookup_id=lookup_id,
            provider=request.provider,
            paper_id=request.paper_id,
            paper=paper,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def _search_pubmed(
        self,
        request: BiomedicalSearchRequest,
    ) -> tuple[list[BiomedicalPaperResultItem], int | None, dict[str, object]]:
        search_response = self._client.get(
            self.config.pubmed_search_api_base_url,
            params={
                "db": "pubmed",
                "term": self._pubmed_term(request.query, request.publication_year),
                "retmode": "json",
                "retmax": request.count,
                "retstart": (request.page - 1) * request.count,
            },
            headers={"Accept": "application/json"},
        )
        search_response.raise_for_status()
        search_payload = search_response.json()
        if not isinstance(search_payload, dict):
            msg = "PubMed search response must be a JSON object."
            raise BiomedicalResearchPluginError(msg)
        esearch = search_payload.get("esearchresult")
        if not isinstance(esearch, dict):
            msg = "PubMed search response missing esearchresult payload."
            raise BiomedicalResearchPluginError(msg)
        id_list = esearch.get("idlist")
        if not isinstance(id_list, list):
            msg = "PubMed search response idlist must be a list."
            raise BiomedicalResearchPluginError(msg)
        article_ids = [item for item in id_list if isinstance(item, str) and item.strip()]
        total = self._to_int(esearch.get("count"))
        if not article_ids:
            return [], total, {"search": search_payload}
        fetch_response = self._client.get(
            self.config.pubmed_fetch_api_base_url,
            params={
                "db": "pubmed",
                "id": ",".join(article_ids),
                "retmode": "xml",
                "rettype": "abstract",
            },
            headers={"Accept": "application/xml, text/xml"},
        )
        fetch_response.raise_for_status()
        results = self._parse_pubmed_articles(fetch_response.text, limit=request.count)
        return results, total, {"search": search_payload, "fetch_xml": fetch_response.text}

    def _get_pubmed_paper(
        self,
        paper_id: str,
    ) -> tuple[BiomedicalPaperResultItem, dict[str, object]]:
        fetch_response = self._client.get(
            self.config.pubmed_fetch_api_base_url,
            params={
                "db": "pubmed",
                "id": paper_id,
                "retmode": "xml",
                "rettype": "abstract",
            },
            headers={"Accept": "application/xml, text/xml"},
        )
        fetch_response.raise_for_status()
        results = self._parse_pubmed_articles(fetch_response.text, limit=1)
        if not results:
            msg = "PubMed paper lookup returned no matching paper."
            raise BiomedicalResearchPluginError(msg)
        return results[0], {"fetch_xml": fetch_response.text}

    def _search_europe_pmc(
        self,
        request: BiomedicalSearchRequest,
    ) -> tuple[list[BiomedicalPaperResultItem], int | None, dict[str, object]]:
        response = self._client.get(
            self.config.europe_pmc_search_api_base_url,
            params={
                "query": self._europe_pmc_query(request.query, request.publication_year),
                "format": "json",
                "resultType": "core",
                "pageSize": request.count,
                "page": request.page,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            msg = "Europe PMC search response must be a JSON object."
            raise BiomedicalResearchPluginError(msg)
        results, total = self._normalize_europe_pmc_results(payload, limit=request.count)
        return results, total, payload

    def _get_europe_pmc_paper(
        self,
        paper_id: str,
    ) -> tuple[BiomedicalPaperResultItem, dict[str, object]]:
        response = self._client.get(
            self.config.europe_pmc_search_api_base_url,
            params={
                "query": f"EXT_ID:{paper_id}",
                "format": "json",
                "resultType": "core",
                "pageSize": 1,
                "page": 1,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            msg = "Europe PMC work response must be a JSON object."
            raise BiomedicalResearchPluginError(msg)
        results, _ = self._normalize_europe_pmc_results(payload, limit=1)
        if not results:
            msg = "Europe PMC paper lookup returned no matching paper."
            raise BiomedicalResearchPluginError(msg)
        return results[0], payload

    def _normalize_europe_pmc_results(
        self,
        payload: dict[str, object],
        *,
        limit: int,
    ) -> tuple[list[BiomedicalPaperResultItem], int | None]:
        total = self._to_int(payload.get("hitCount"))
        result_list = payload.get("resultList")
        if not isinstance(result_list, dict):
            msg = "Europe PMC response missing resultList payload."
            raise BiomedicalResearchPluginError(msg)
        raw_results = result_list.get("result")
        if not isinstance(raw_results, list):
            msg = "Europe PMC results must be a list."
            raise BiomedicalResearchPluginError(msg)
        results: list[BiomedicalPaperResultItem] = []
        for raw_item in raw_results:
            if len(results) >= limit:
                break
            if not isinstance(raw_item, dict):
                continue
            results.append(self._normalize_europe_pmc_item(raw_item))
        return results, total

    def _normalize_europe_pmc_item(self, payload: dict[str, object]) -> BiomedicalPaperResultItem:
        paper_id = self._first_string(payload.get("id"), payload.get("pmid"), payload.get("pmcid"))
        if paper_id is None:
            msg = "Europe PMC paper is missing id."
            raise BiomedicalResearchPluginError(msg)
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            msg = "Europe PMC paper is missing title."
            raise BiomedicalResearchPluginError(msg)
        pmid = self._string_or_none(payload.get("pmid"))
        pmcid = self._string_or_none(payload.get("pmcid"))
        abstract = self._string_or_none(payload.get("abstractText")) or ""
        author_string = self._string_or_none(payload.get("authorString"))
        authors = self._split_author_string(author_string)
        return BiomedicalPaperResultItem(
            provider="europe_pmc",
            paper_id=paper_id,
            title=title.strip(),
            abstract=abstract[: self.config.max_abstract_chars],
            authors=authors,
            journal=self._string_or_none(payload.get("journalTitle")),
            publication_year=self._to_int(payload.get("pubYear")),
            publication_date=self._string_or_none(payload.get("firstPublicationDate")),
            doi=self._string_or_none(payload.get("doi")),
            pmid=pmid,
            pmcid=pmcid,
            cited_by_count=self._to_int(payload.get("citedByCount")),
            is_open_access=self._bool_from_yn(payload.get("isOpenAccess")),
            source_url=self._europe_pmc_source_url(pmid, pmcid),
        )

    def _parse_pubmed_articles(
        self,
        xml_text: str,
        *,
        limit: int,
    ) -> list[BiomedicalPaperResultItem]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as error:
            msg = "PubMed response must be valid XML."
            raise BiomedicalResearchPluginError(msg) from error
        articles = root.findall("./PubmedArticle")
        results: list[BiomedicalPaperResultItem] = []
        for article in articles:
            if len(results) >= limit:
                break
            results.append(self._parse_pubmed_article(article))
        return results

    def _parse_pubmed_article(self, article: ET.Element) -> BiomedicalPaperResultItem:
        medline = article.find("./MedlineCitation")
        article_node = article.find("./MedlineCitation/Article")
        if medline is None or article_node is None:
            msg = "PubMed article payload is missing core article data."
            raise BiomedicalResearchPluginError(msg)
        pmid = self._required_xml_text(medline, "./PMID", "PubMed article PMID")
        title = self._required_xml_text(article_node, "./ArticleTitle", "PubMed article title")
        abstract = self._pubmed_abstract(article_node)
        authors = self._pubmed_authors(article_node)
        journal_title = self._optional_xml_text(article_node, "./Journal/Title")
        publication_year = self._to_int(
            self._optional_xml_text(article_node, "./Journal/JournalIssue/PubDate/Year")
        )
        publication_date = self._pubmed_publication_date(article_node)
        doi, pmcid = self._pubmed_identifiers(article)
        return BiomedicalPaperResultItem(
            provider="pubmed",
            paper_id=pmid,
            title=title,
            abstract=abstract[: self.config.max_abstract_chars],
            authors=authors,
            journal=journal_title,
            publication_year=publication_year,
            publication_date=publication_date,
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        )

    def _pubmed_identifiers(self, article: ET.Element) -> tuple[str | None, str | None]:
        doi: str | None = None
        pmcid: str | None = None
        for id_node in article.findall("./PubmedData/ArticleIdList/ArticleId"):
            id_type = (id_node.attrib.get("IdType") or "").strip().lower()
            value = self._xml_text(id_node)
            if not value:
                continue
            if id_type == "doi":
                doi = value
            elif id_type == "pmc":
                pmcid = value
        return doi, pmcid

    def _pubmed_abstract(self, article_node: ET.Element) -> str:
        abstract_nodes = article_node.findall("./Abstract/AbstractText")
        parts: list[str] = []
        for node in abstract_nodes:
            text = self._xml_text(node)
            if not text:
                continue
            label = (node.attrib.get("Label") or "").strip()
            parts.append(f"{label}: {text}" if label else text)
        return " ".join(parts)

    def _pubmed_authors(self, article_node: ET.Element) -> list[str]:
        authors: list[str] = []
        for author_node in article_node.findall("./AuthorList/Author"):
            collective = self._optional_xml_text(author_node, "./CollectiveName")
            if collective is not None:
                authors.append(collective)
                continue
            last_name = self._optional_xml_text(author_node, "./LastName")
            fore_name = self._optional_xml_text(author_node, "./ForeName")
            if last_name and fore_name:
                authors.append(f"{fore_name} {last_name}")
            elif last_name:
                authors.append(last_name)
        return authors

    def _pubmed_publication_date(self, article_node: ET.Element) -> str | None:
        year = self._optional_xml_text(article_node, "./Journal/JournalIssue/PubDate/Year")
        month = self._optional_xml_text(article_node, "./Journal/JournalIssue/PubDate/Month")
        day = self._optional_xml_text(article_node, "./Journal/JournalIssue/PubDate/Day")
        if year is None:
            return self._optional_xml_text(
                article_node,
                "./Journal/JournalIssue/PubDate/MedlineDate",
            )
        if month is None:
            return year
        if day is None:
            return f"{year}-{month}"
        return f"{year}-{month}-{day}"

    def _record_failure(self, lookup_id: str, event_name: str, **payload: object) -> None:
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=lookup_id,
            event_name=event_name,
            payload=payload,
        )

    @staticmethod
    def _provider_label(provider: str) -> str:
        return "Europe PMC" if provider == "europe_pmc" else "PubMed"

    @staticmethod
    def _pubmed_term(query: str, publication_year: int | None) -> str:
        normalized = " ".join(query.split())
        if publication_year is None:
            return normalized
        return f"{normalized} AND {publication_year}[pdat]"

    @staticmethod
    def _europe_pmc_query(query: str, publication_year: int | None) -> str:
        normalized = " ".join(query.split())
        if publication_year is None:
            return normalized
        return f"{normalized} PUB_YEAR:{publication_year}"

    @staticmethod
    def _to_int(value: object) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    @staticmethod
    def _bool_from_yn(value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized == "Y":
                return True
            if normalized == "N":
                return False
        return None

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _first_string(*values: object) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _split_author_string(value: str | None) -> list[str]:
        if value is None:
            return []
        return [item.strip() for item in value.split(";") if item.strip()]

    @staticmethod
    def _europe_pmc_source_url(pmid: str | None, pmcid: str | None) -> str | None:
        if pmcid is not None:
            return f"https://europepmc.org/article/PMC/{pmcid}"
        if pmid is not None:
            return f"https://europepmc.org/article/MED/{pmid}"
        return None

    @staticmethod
    def _xml_text(node: ET.Element) -> str:
        return " ".join("".join(node.itertext()).split())

    def _required_xml_text(self, node: ET.Element, path: str, description: str) -> str:
        child = node.find(path)
        if child is None:
            msg = f"PubMed response missing {description}."
            raise BiomedicalResearchPluginError(msg)
        text = self._xml_text(child)
        if not text:
            msg = f"PubMed response missing {description}."
            raise BiomedicalResearchPluginError(msg)
        return text

    def _optional_xml_text(self, node: ET.Element, path: str) -> str | None:
        child = node.find(path)
        if child is None:
            return None
        text = self._xml_text(child)
        return text or None
