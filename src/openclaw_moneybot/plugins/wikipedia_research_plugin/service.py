"""Read-only Wikipedia research integration."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.plugins.wikipedia_research_plugin.models import (
    WikipediaPageRequest,
    WikipediaPageResult,
    WikipediaSearchRequest,
    WikipediaSearchResult,
    WikipediaSearchResultItem,
)
from openclaw_moneybot.shared import ArchiveConfig, WikipediaResearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class WikipediaResearchPluginError(RuntimeError):
    """Raised when Wikipedia research cannot be completed safely."""


class WikipediaResearchPlugin:
    """Search and summarize Wikipedia through bounded read-only APIs."""

    def __init__(
        self,
        config: WikipediaResearchConfig,
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
            plugin_name="wikipedia_research_plugin",
            enabled=self.config.enabled,
            read_only=True,
        )

    def search(self, request: WikipediaSearchRequest) -> WikipediaSearchResult:
        """Execute one bounded Wikipedia title search."""

        if not self.config.enabled:
            msg = "wikipedia_research_plugin is disabled."
            raise ValueError(msg)
        if request.count > self.config.max_results:
            msg = "Requested result count exceeds the configured maximum."
            raise ValueError(msg)
        lookup_id = make_id("wikipedia")
        language = request.language or self.config.default_language
        try:
            response = self._client.get(
                self._api_url(language),
                params={
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": request.query,
                    "srlimit": request.count,
                    "utf8": "1",
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(lookup_id, "wikipedia_search_failed", query=request.query)
            msg = "Wikipedia search is unavailable."
            raise WikipediaResearchPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            self._record_failure(lookup_id, "wikipedia_search_failed", query=request.query)
            msg = f"Wikipedia search request failed: {error}"
            raise WikipediaResearchPluginError(msg) from error
        if not isinstance(payload, dict):
            msg = "Wikipedia search response must be a JSON object."
            raise WikipediaResearchPluginError(msg)
        results = self._normalize_search_results(payload, language=language, limit=request.count)
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.WIKIPEDIA_RESEARCH,
            related_id=lookup_id,
            evidence_type="wikipedia_search_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded Wikipedia search response snapshot",
        )
        summary = {
            "query": request.query,
            "language": language,
            "result_titles": [item.title for item in results],
            "result_urls": [str(item.url) for item in results],
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.WIKIPEDIA_RESEARCH,
            related_record_id=lookup_id,
            payload={
                "mode": "search",
                "query": request.query,
                "language": language,
                "result_count": len(results),
                "result_titles": [item.title for item in results],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return WikipediaSearchResult(
            lookup_id=lookup_id,
            query=request.query,
            language=language,
            results=results,
            result_count=len(results),
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def get_page_summary(self, request: WikipediaPageRequest) -> WikipediaPageResult:
        """Fetch one bounded Wikipedia page summary."""

        if not self.config.enabled:
            msg = "wikipedia_research_plugin is disabled."
            raise ValueError(msg)
        lookup_id = make_id("wikipedia")
        language = request.language or self.config.default_language
        max_extract_chars = (
            self.config.max_extract_chars
            if request.max_extract_chars is None
            else min(request.max_extract_chars, self.config.max_extract_chars)
        )
        try:
            response = self._client.get(
                self._summary_url(language, request.title),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(lookup_id, "wikipedia_summary_failed", title=request.title)
            msg = "Wikipedia summary is unavailable."
            raise WikipediaResearchPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            self._record_failure(lookup_id, "wikipedia_summary_failed", title=request.title)
            msg = f"Wikipedia summary request failed: {error}"
            raise WikipediaResearchPluginError(msg) from error
        if not isinstance(payload, dict):
            msg = "Wikipedia summary response must be a JSON object."
            raise WikipediaResearchPluginError(msg)

        normalized = self._normalize_page_summary(
            payload,
            language=language,
            max_extract_chars=max_extract_chars,
        )
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.WIKIPEDIA_RESEARCH,
            related_id=lookup_id,
            evidence_type="wikipedia_page_summary_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded Wikipedia page summary snapshot",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=lookup_id,
            record_type=RecordType.WIKIPEDIA_RESEARCH,
            related_record_id=lookup_id,
            payload={
                "mode": "page_summary",
                "title": str(normalized["title"]),
                "language": language,
                "canonical_url": str(normalized["canonical_url"]),
                "page_id": normalized["page_id"],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return WikipediaPageResult.model_validate(
            {
                **normalized,
                "lookup_id": lookup_id,
                "evidence_archive_ids": [evidence_id],
                "ledger_record": ledger_record,
            }
        )

    def _record_failure(self, lookup_id: str, event_name: str, **payload: object) -> None:
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=lookup_id,
            event_name=event_name,
            payload=payload,
        )

    def _api_url(self, language: str) -> str:
        return self.config.api_base_url.replace("en.wikipedia.org", f"{language}.wikipedia.org")

    def _summary_url(self, language: str, title: str) -> str:
        base = self.config.summary_api_base_url.replace(
            "en.wikipedia.org",
            f"{language}.wikipedia.org",
        )
        return f"{base}/{quote(title.replace(' ', '_'), safe='')}"

    @staticmethod
    def _normalize_search_results(
        payload: dict[str, object],
        *,
        language: str,
        limit: int,
    ) -> list[WikipediaSearchResultItem]:
        query = payload.get("query")
        if not isinstance(query, dict):
            msg = "Wikipedia search response missing query payload."
            raise WikipediaResearchPluginError(msg)
        search = query.get("search")
        if not isinstance(search, list):
            msg = "Wikipedia search results must be a list."
            raise WikipediaResearchPluginError(msg)
        results: list[WikipediaSearchResultItem] = []
        for item in search:
            if len(results) >= limit:
                break
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            page_id = item.get("pageid")
            if not isinstance(title, str) or not isinstance(page_id, int):
                continue
            snippet = item.get("snippet")
            results.append(
                WikipediaSearchResultItem.model_validate(
                    {
                        "title": title,
                        "page_id": page_id,
                        "url": (
                            f"https://{language}.wikipedia.org/wiki/"
                            f"{quote(title.replace(' ', '_'))}"
                        ),
                        "snippet": snippet if isinstance(snippet, str) else "",
                    }
                )
            )
        return results

    @staticmethod
    def _normalize_page_summary(
        payload: dict[str, object],
        *,
        language: str,
        max_extract_chars: int,
    ) -> dict[str, object]:
        title = payload.get("title")
        extract = payload.get("extract")
        content_urls = payload.get("content_urls")
        if not isinstance(title, str) or not isinstance(extract, str) or not isinstance(
            content_urls, dict
        ):
            msg = "Wikipedia summary payload is missing required fields."
            raise WikipediaResearchPluginError(msg)
        desktop = content_urls.get("desktop")
        page_url = desktop.get("page") if isinstance(desktop, dict) else None
        if not isinstance(page_url, str):
            msg = "Wikipedia summary payload missing canonical page URL."
            raise WikipediaResearchPluginError(msg)
        page_id = payload.get("pageid")
        revision = payload.get("revision")
        timestamp = payload.get("timestamp")
        json_content_urls = {
            key: value for key, value in content_urls.items() if isinstance(key, str)
        }
        return {
            "title": title,
            "canonical_url": page_url,
            "language": language,
            "summary": extract[:max_extract_chars],
            "page_id": page_id if isinstance(page_id, int) else None,
            "revision": revision if isinstance(revision, int) else None,
            "last_modified": timestamp if isinstance(timestamp, str) else None,
            "content_urls": json_content_urls,
            "raw_response_summary": {
                "title": title,
                "language": language,
                "canonical_url": page_url,
                "summary_length": min(len(extract), max_extract_chars),
            },
        }
