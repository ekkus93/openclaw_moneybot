"""Read-only Brave Search integration."""

from __future__ import annotations

import os

import httpx
from pydantic import JsonValue

from openclaw_moneybot.plugins.brave_search_plugin.models import (
    BraveNewsSearchRequest,
    BraveSearchRequest,
    BraveSearchResult,
    BraveSearchResultItem,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, BraveSearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class BraveSearchPluginError(RuntimeError):
    """Raised when Brave Search cannot be used safely."""


class BraveSearchPlugin:
    """Run bounded Brave Search queries through the hosted API."""

    def __init__(
        self,
        config: BraveSearchConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
        self.ledger_service = ledger_service
        self._client = httpx.Client(
            timeout=config.timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def health(self) -> PluginHealthResult:
        """Return plugin status, including missing credential state."""

        return PluginHealthResult(
            plugin_name="brave_search_plugin",
            enabled=self.config.enabled,
            read_only=True,
            status="ok" if self._api_key() is not None else "missing_api_key",
        )

    def search(self, request: BraveSearchRequest) -> BraveSearchResult:
        """Execute one bounded Brave Search query."""

        return self._search(
            request_query=request.query,
            count=request.count,
            country=request.country,
            search_lang=request.search_lang,
            safesearch=request.safesearch,
            freshness=request.freshness,
            mode="web",
            source_domains=[],
            raw_request=request.model_dump(mode="json"),
        )

    def search_news(self, request: BraveNewsSearchRequest) -> BraveSearchResult:
        """Execute one bounded current-events/news query through Brave web search."""

        if request.count > self.config.max_news_results:
            msg = "Requested news result count exceeds the configured maximum."
            raise ValueError(msg)
        freshness = request.freshness or self.config.default_news_freshness
        news_query = self._news_query(request.query, request.source_domains)
        return self._search(
            request_query=news_query,
            count=request.count,
            country=request.country,
            search_lang=request.search_lang,
            safesearch=request.safesearch,
            freshness=freshness,
            mode="news",
            source_domains=request.source_domains,
            raw_request=request.model_dump(mode="json"),
        )

    def _search(
        self,
        *,
        request_query: str,
        count: int,
        country: str | None,
        search_lang: str | None,
        safesearch: str | None,
        freshness: str | None,
        mode: str,
        source_domains: list[str],
        raw_request: dict[str, JsonValue],
    ) -> BraveSearchResult:
        """Execute one bounded Brave Search query mode."""

        if not self.config.enabled:
            msg = "brave_search_plugin is disabled."
            raise ValueError(msg)
        api_key = self._api_key()
        if api_key is None:
            msg = f"Missing Brave Search API key in {self.config.api_key_env_var}."
            raise BraveSearchPluginError(msg)
        if mode == "web" and count > self.config.max_results:
            msg = "Requested result count exceeds the configured maximum."
            raise ValueError(msg)

        search_id = make_id("web_search")
        try:
            response = self._client.get(
                self.config.api_base_url,
                params={
                    "q": request_query,
                    "count": count,
                    "country": country or self.config.default_country,
                    "search_lang": search_lang or self.config.default_search_lang,
                    "safesearch": safesearch or self.config.safesearch,
                    **(
                        {}
                        if freshness is None
                        else {"freshness": freshness}
                    ),
                },
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            record_plugin_audit_event(
                self.ledger_service,
                related_record_id=search_id,
                event_name=f"brave_{mode}_search_failed",
                payload={"query": request_query, "reason": "transport_error"},
            )
            msg = "Brave Search is unavailable."
            raise BraveSearchPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            record_plugin_audit_event(
                self.ledger_service,
                related_record_id=search_id,
                event_name=f"brave_{mode}_search_failed",
                payload={"query": request_query, "reason": "invalid_response"},
            )
            msg = f"Brave Search request failed: {error}"
            raise BraveSearchPluginError(msg) from error

        if not isinstance(payload, dict):
            msg = "Brave Search response must be a JSON object."
            raise BraveSearchPluginError(msg)
        results = self._normalize_results(payload, limit=count)
        raw_summary = {
            "query": request_query,
            "country": country or self.config.default_country,
            "search_lang": search_lang or self.config.default_search_lang,
            "safesearch": safesearch or self.config.safesearch,
            "mode": mode,
            "freshness": freshness,
            "source_domains": source_domains,
            "reported_total": self._reported_total(payload),
            "result_urls": [str(item.url) for item in results],
        }
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.WEB_SEARCH,
            related_id=search_id,
            evidence_type=f"brave_{mode}_search_response",
            payload={
                "request": raw_request,
                "response": payload,
            },
            notes=f"Bounded Brave {mode} search response snapshot",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=search_id,
            record_type=RecordType.WEB_SEARCH,
            related_record_id=search_id,
            payload={
                "provider": "brave_search",
                "query": request_query,
                "mode": mode,
                "result_count": len(results),
                "freshness": freshness,
                "source_domains": source_domains,
                "result_urls": [str(item.url) for item in results],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return BraveSearchResult(
            search_id=search_id,
            query=request_query,
            results=results,
            mode="web" if mode == "web" else "news",
            result_count=len(results),
            freshness=freshness,
            source_domains=source_domains,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=raw_summary,
            ledger_record=ledger_record,
        )

    def _api_key(self) -> str | None:
        api_key = os.environ.get(self.config.api_key_env_var)
        if api_key is None:
            return None
        normalized = api_key.strip()
        return None if normalized == "" else normalized

    @staticmethod
    def _reported_total(payload: dict[str, object]) -> int | None:
        web = payload.get("web")
        if not isinstance(web, dict):
            return None
        total = web.get("total")
        if isinstance(total, int):
            return total
        return None

    @staticmethod
    def _normalize_results(
        payload: dict[str, object],
        *,
        limit: int,
    ) -> list[BraveSearchResultItem]:
        web = payload.get("web")
        if not isinstance(web, dict):
            msg = "Brave Search response missing web results."
            raise BraveSearchPluginError(msg)
        raw_results = web.get("results")
        if not isinstance(raw_results, list):
            msg = "Brave Search web results must be a list."
            raise BraveSearchPluginError(msg)
        normalized: list[BraveSearchResultItem] = []
        for raw_item in raw_results:
            if len(normalized) >= limit:
                break
            if not isinstance(raw_item, dict):
                continue
            url = raw_item.get("url")
            title = raw_item.get("title")
            if not isinstance(url, str) or not isinstance(title, str):
                continue
            result_payload: dict[str, JsonValue] = {
                "title": title,
                "url": url,
                "description": (
                    raw_item["description"] if isinstance(raw_item.get("description"), str) else ""
                ),
                "age": raw_item["age"] if isinstance(raw_item.get("age"), str) else None,
                "language": (
                    raw_item["language"] if isinstance(raw_item.get("language"), str) else None
                ),
                "family_friendly": (
                    raw_item["family_friendly"]
                    if isinstance(raw_item.get("family_friendly"), bool)
                    else None
                ),
            }
            normalized.append(BraveSearchResultItem.model_validate(result_payload))
        return normalized

    @staticmethod
    def _news_query(query: str, source_domains: list[str]) -> str:
        if not source_domains:
            return query
        site_filters = " OR ".join(f"site:{domain}" for domain in source_domains)
        return f"{query} ({site_filters})"
