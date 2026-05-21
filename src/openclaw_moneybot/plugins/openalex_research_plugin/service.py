"""Read-only OpenAlex research integration."""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx

from openclaw_moneybot.plugins.openalex_research_plugin.models import (
    OpenAlexSearchRequest,
    OpenAlexSearchResult,
    OpenAlexWorkRequest,
    OpenAlexWorkResult,
    OpenAlexWorkResultItem,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, OpenAlexResearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class OpenAlexResearchPluginError(RuntimeError):
    """Raised when OpenAlex research cannot be completed safely."""


class OpenAlexResearchPlugin:
    """Search and fetch scholarly works through the bounded OpenAlex API."""

    def __init__(
        self,
        config: OpenAlexResearchConfig,
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
        """Return plugin status, including missing credential state."""

        return PluginHealthResult(
            plugin_name="openalex_research_plugin",
            enabled=self.config.enabled,
            read_only=True,
            status="ok" if self._api_key() is not None else "missing_api_key",
        )

    def search(self, request: OpenAlexSearchRequest) -> OpenAlexSearchResult:
        """Execute one bounded OpenAlex works search."""

        if not self.config.enabled:
            msg = "openalex_research_plugin is disabled."
            raise ValueError(msg)
        if request.count > self.config.max_results:
            msg = "Requested result count exceeds the configured maximum."
            raise ValueError(msg)
        api_key = self._api_key()
        if api_key is None:
            msg = f"Missing OpenAlex API key in {self.config.api_key_env_var}."
            raise OpenAlexResearchPluginError(msg)
        lookup_id = make_id("openalex")
        try:
            response = self._client.get(
                self.config.api_base_url,
                params={
                    "search": request.query,
                    "per_page": request.count,
                    "page": request.page,
                    "api_key": api_key,
                    **self._search_filter_params(request),
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(lookup_id, "openalex_search_failed", query=request.query)
            msg = "OpenAlex search is unavailable."
            raise OpenAlexResearchPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            self._record_failure(lookup_id, "openalex_search_failed", query=request.query)
            msg = f"OpenAlex search request failed: {error}"
            raise OpenAlexResearchPluginError(msg) from error
        if not isinstance(payload, dict):
            msg = "OpenAlex search response must be a JSON object."
            raise OpenAlexResearchPluginError(msg)
        results, total_results = self._normalize_search_results(payload, limit=request.count)
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.OPENALEX_RESEARCH,
            related_id=lookup_id,
            evidence_type="openalex_search_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded OpenAlex search response snapshot",
        )
        summary = {
            "query": request.query,
            "page": request.page,
            "publication_year": request.publication_year,
            "open_access_only": request.open_access_only,
            "result_ids": [str(item.work_id) for item in results],
            "result_titles": [item.title for item in results],
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.OPENALEX_RESEARCH,
            related_record_id=lookup_id,
            payload={
                "mode": "search",
                "query": request.query,
                "page": request.page,
                "publication_year": request.publication_year,
                "open_access_only": request.open_access_only,
                "result_count": len(results),
                "total_results": total_results,
                "result_ids": [str(item.work_id) for item in results],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return OpenAlexSearchResult(
            lookup_id=lookup_id,
            query=request.query,
            page=request.page,
            result_count=len(results),
            total_results=total_results,
            publication_year=request.publication_year,
            open_access_only=request.open_access_only,
            results=results,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def get_work(self, request: OpenAlexWorkRequest) -> OpenAlexWorkResult:
        """Fetch one bounded OpenAlex work."""

        if not self.config.enabled:
            msg = "openalex_research_plugin is disabled."
            raise ValueError(msg)
        api_key = self._api_key()
        if api_key is None:
            msg = f"Missing OpenAlex API key in {self.config.api_key_env_var}."
            raise OpenAlexResearchPluginError(msg)
        lookup_id = make_id("openalex")
        try:
            response = self._client.get(
                f"{self.config.api_base_url}/{self._work_lookup_path(request.work_id)}",
                params={"api_key": api_key},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(lookup_id, "openalex_work_lookup_failed", work_id=request.work_id)
            msg = "OpenAlex work lookup is unavailable."
            raise OpenAlexResearchPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            self._record_failure(lookup_id, "openalex_work_lookup_failed", work_id=request.work_id)
            msg = f"OpenAlex work lookup request failed: {error}"
            raise OpenAlexResearchPluginError(msg) from error
        if not isinstance(payload, dict):
            msg = "OpenAlex work response must be a JSON object."
            raise OpenAlexResearchPluginError(msg)

        work = self._normalize_work(payload)
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.OPENALEX_RESEARCH,
            related_id=lookup_id,
            evidence_type="openalex_work_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded OpenAlex work lookup response snapshot",
        )
        summary = {
            "work_id": str(work.work_id),
            "title": work.title,
            "doi": str(work.doi) if work.doi is not None else None,
            "cited_by_count": work.cited_by_count,
            "primary_topic": work.primary_topic,
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.OPENALEX_RESEARCH,
            related_record_id=lookup_id,
            payload={
                "mode": "work_lookup",
                "work_id": str(work.work_id),
                "title": work.title,
                "doi": str(work.doi) if work.doi is not None else None,
                "evidence_archive_ids": [evidence_id],
            },
        )
        return OpenAlexWorkResult(
            lookup_id=lookup_id,
            work_id=request.work_id,
            work=work,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def _api_key(self) -> str | None:
        api_key = os.environ.get(self.config.api_key_env_var)
        if api_key is None:
            return None
        normalized = api_key.strip()
        return None if normalized == "" else normalized

    def _record_failure(self, lookup_id: str, event_name: str, **payload: object) -> None:
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=lookup_id,
            event_name=event_name,
            payload=payload,
        )

    @staticmethod
    def _search_filter_params(request: OpenAlexSearchRequest) -> dict[str, str]:
        filters: list[str] = []
        if request.publication_year is not None:
            filters.append(f"publication_year:{request.publication_year}")
        if request.open_access_only:
            filters.append("is_oa:true")
        return {} if not filters else {"filter": ",".join(filters)}

    @staticmethod
    def _work_lookup_path(work_id: str) -> str:
        normalized = work_id.strip()
        if normalized.startswith("https://openalex.org/"):
            normalized = normalized.rsplit("/", maxsplit=1)[-1]
        return quote(normalized, safe="")

    def _normalize_search_results(
        self,
        payload: dict[str, object],
        *,
        limit: int,
    ) -> tuple[list[OpenAlexWorkResultItem], int | None]:
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            msg = "OpenAlex search response missing meta payload."
            raise OpenAlexResearchPluginError(msg)
        total_results = meta.get("count")
        if not isinstance(total_results, int):
            total_results = None
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            msg = "OpenAlex search results must be a list."
            raise OpenAlexResearchPluginError(msg)
        normalized: list[OpenAlexWorkResultItem] = []
        for raw_item in raw_results:
            if len(normalized) >= limit:
                break
            if not isinstance(raw_item, dict):
                continue
            normalized.append(self._normalize_work(raw_item))
        return normalized, total_results

    def _normalize_work(self, payload: dict[str, object]) -> OpenAlexWorkResultItem:
        work_id = payload.get("id")
        if not isinstance(work_id, str):
            msg = "OpenAlex work is missing id."
            raise OpenAlexResearchPluginError(msg)
        title = payload.get("display_name")
        if not isinstance(title, str) or not title.strip():
            raw_title = payload.get("title")
            if not isinstance(raw_title, str) or not raw_title.strip():
                msg = "OpenAlex work is missing display_name."
                raise OpenAlexResearchPluginError(msg)
            title = raw_title
        doi = payload.get("doi")
        publication_year = payload.get("publication_year")
        publication_date = payload.get("publication_date")
        work_type = payload.get("type")
        language = payload.get("language")
        cited_by_count = payload.get("cited_by_count")
        authors = self._authors(payload.get("authorships"))
        primary_topic = self._display_name_from_mapping(payload.get("primary_topic"))
        topics = self._topics(payload.get("topics"))
        primary_location = self._mapping(payload.get("primary_location"))
        best_oa_location = self._mapping(payload.get("best_oa_location"))
        open_access = self._mapping(payload.get("open_access"))
        landing_page_url = self._first_string(
            self._get_nested(primary_location, "landing_page_url"),
            self._get_nested(best_oa_location, "landing_page_url"),
            self._get_nested(open_access, "oa_url"),
        )
        pdf_url = self._first_string(
            self._get_nested(primary_location, "pdf_url"),
            self._get_nested(best_oa_location, "pdf_url"),
        )
        source_display_name = self._display_name_from_mapping(
            self._get_nested(primary_location, "source")
        )
        if source_display_name is None:
            source_display_name = self._display_name_from_mapping(
                self._get_nested(best_oa_location, "source")
            )
        return OpenAlexWorkResultItem(
            work_id=work_id,
            title=title.strip(),
            doi=doi if isinstance(doi, str) else None,
            publication_year=publication_year if isinstance(publication_year, int) else None,
            publication_date=publication_date if isinstance(publication_date, str) else None,
            work_type=work_type if isinstance(work_type, str) else None,
            language=language if isinstance(language, str) else None,
            cited_by_count=cited_by_count if isinstance(cited_by_count, int) else 0,
            is_open_access=(
                open_access.get("is_oa")
                if isinstance(open_access.get("is_oa"), bool)
                else None
            ),
            oa_status=(
                open_access.get("oa_status")
                if isinstance(open_access.get("oa_status"), str)
                else None
            ),
            abstract=self._abstract_text(payload.get("abstract_inverted_index")),
            authors=authors,
            primary_topic=primary_topic,
            topics=topics,
            source_display_name=source_display_name,
            landing_page_url=landing_page_url,
            pdf_url=pdf_url,
        )

    def _abstract_text(self, inverted_index: object) -> str:
        if not isinstance(inverted_index, dict):
            return ""
        ordered_words: list[str | None] = []
        for word, positions in inverted_index.items():
            if not isinstance(word, str) or not isinstance(positions, list):
                continue
            for position in positions:
                if not isinstance(position, int) or position < 0:
                    continue
                if position >= 10_000:
                    continue
                while len(ordered_words) <= position:
                    ordered_words.append(None)
                ordered_words[position] = word
        text = " ".join(word for word in ordered_words if word)
        return text[: self.config.max_abstract_chars]

    @staticmethod
    def _authors(authorships: object) -> list[str]:
        if not isinstance(authorships, list):
            return []
        authors: list[str] = []
        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author")
            if not isinstance(author, dict):
                continue
            display_name = author.get("display_name")
            if isinstance(display_name, str) and display_name.strip():
                authors.append(display_name.strip())
        return authors

    @staticmethod
    def _topics(topics: object) -> list[str]:
        if not isinstance(topics, list):
            return []
        values: list[str] = []
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            display_name = topic.get("display_name")
            if isinstance(display_name, str) and display_name.strip():
                values.append(display_name.strip())
        return values[:5]

    @staticmethod
    def _display_name_from_mapping(value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        display_name = value.get("display_name")
        if not isinstance(display_name, str):
            return None
        normalized = display_name.strip()
        return normalized or None

    @staticmethod
    def _mapping(value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _get_nested(mapping: dict[str, object], key: str) -> object:
        return mapping.get(key)

    @staticmethod
    def _first_string(*values: object) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
