"""Unit tests for the Wikipedia research plugin."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

import openclaw_moneybot.plugins.wikipedia_research_plugin.service as wikipedia_service
from openclaw_moneybot.plugins.wikipedia_research_plugin import (
    WikipediaPageRequest,
    WikipediaResearchPlugin,
    WikipediaResearchPluginError,
    WikipediaSearchRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, WikipediaResearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(
    tmp_path: Path,
    *,
    enabled: bool = True,
    handler: httpx.BaseTransport | None = None,
) -> tuple[WikipediaResearchPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = WikipediaResearchPlugin(
        WikipediaResearchConfig(enabled=enabled, max_results=5, max_extract_chars=120),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def audit_event_payloads(ledger_service: LedgerService) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for event in ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT):
        payload = event.payload.get("payload")
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def test_search_returns_bounded_normalized_results(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "en.wikipedia.org"
        assert request.url.params["srsearch"] == "Ada Lovelace"
        return httpx.Response(
            200,
            json={
                "query": {
                    "search": [
                        {
                            "title": "Ada Lovelace",
                            "pageid": 12_345,
                            "snippet": "English mathematician and writer",
                        }
                    ]
                }
            },
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.search(WikipediaSearchRequest(query="Ada Lovelace", count=1))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.WIKIPEDIA_RESEARCH,
        related_id=result.lookup_id,
    )

    assert result.query == "Ada Lovelace"
    assert result.language == "en"
    assert result.result_count == 1
    assert result.results[0].title == "Ada Lovelace"
    assert result.results[0].page_id == 12_345
    assert evidence[0].evidence_type == "wikipedia_search_response"


def test_wikipedia_request_models_normalize_blank_languages_to_none() -> None:
    search_request = WikipediaSearchRequest(query="Ada Lovelace", language=" EN ")
    page_request = WikipediaPageRequest(title="Ada Lovelace", language=" ")

    assert search_request.language == "en"
    assert page_request.language is None


def test_get_page_summary_returns_bounded_summary_and_metadata(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "en.wikipedia.org"
        assert request.url.path.endswith("/Ada_Lovelace")
        return httpx.Response(
            200,
            json={
                "title": "Ada Lovelace",
                "pageid": 12_345,
                "revision": 777,
                "timestamp": "2026-01-01T00:00:00Z",
                "extract": "Ada Lovelace was an English mathematician and writer " * 10,
                "content_urls": {
                    "desktop": {"page": "https://en.wikipedia.org/wiki/Ada_Lovelace"}
                },
            },
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.get_page_summary(WikipediaPageRequest(title="Ada Lovelace"))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.WIKIPEDIA_RESEARCH,
        related_id=result.lookup_id,
    )

    assert result.title == "Ada Lovelace"
    assert result.page_id == 12_345
    assert result.revision == 777
    assert result.last_modified == "2026-01-01T00:00:00Z"
    assert len(result.summary) == 120
    assert str(result.canonical_url) == "https://en.wikipedia.org/wiki/Ada_Lovelace"
    assert evidence[0].evidence_type == "wikipedia_page_summary_response"


def test_search_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.search(WikipediaSearchRequest(query="Ada Lovelace"))


def test_summary_rejects_malformed_payloads(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"title": "Ada Lovelace"})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(WikipediaResearchPluginError, match="required fields"):
        plugin.get_page_summary(WikipediaPageRequest(title="Ada Lovelace"))


def test_search_surfaces_transport_failures_as_plugin_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(WikipediaResearchPluginError, match="unavailable"):
        plugin.search(WikipediaSearchRequest(query="Ada Lovelace"))


def test_search_and_summary_enforce_limits_and_disabled_paths(tmp_path: Path) -> None:
    enabled_plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="configured maximum"):
        enabled_plugin.search(WikipediaSearchRequest(query="Ada Lovelace", count=6))

    disabled_path = tmp_path / "disabled"
    disabled_path.mkdir()
    disabled_plugin, _ = make_plugin(disabled_path, enabled=False)
    with pytest.raises(ValueError, match="disabled"):
        disabled_plugin.get_page_summary(WikipediaPageRequest(title="Ada Lovelace"))


@pytest.mark.parametrize(
    ("handler", "method", "match_text"),
    [
        (lambda request: httpx.Response(500), "search", "request failed"),
        (lambda request: httpx.Response(200, text="{bad-json}"), "search", "request failed"),
        (lambda request: httpx.Response(500), "summary", "request failed"),
        (lambda request: httpx.Response(200, text="{bad-json}"), "summary", "request failed"),
    ],
)
def test_search_and_summary_record_failures_for_invalid_http_or_json(
    tmp_path: Path,
    handler: Callable[[httpx.Request], httpx.Response],
    method: str,
    match_text: str,
) -> None:
    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(WikipediaResearchPluginError, match=match_text):
        if method == "search":
            plugin.search(WikipediaSearchRequest(query="Ada Lovelace"))
        else:
            plugin.get_page_summary(WikipediaPageRequest(title="Ada Lovelace"))

    assert audit_event_payloads(ledger_service)[-1]["event_name"] in {
        "wikipedia_search_failed",
        "wikipedia_summary_failed",
    }


def test_search_and_summary_reject_non_object_top_level_payloads(tmp_path: Path) -> None:
    search_plugin, _ = make_plugin(
        tmp_path / "search",
        handler=httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
    )
    summary_plugin, _ = make_plugin(
        tmp_path / "summary",
        handler=httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
    )

    with pytest.raises(WikipediaResearchPluginError, match="JSON object"):
        search_plugin.search(WikipediaSearchRequest(query="Ada Lovelace"))
    with pytest.raises(WikipediaResearchPluginError, match="JSON object"):
        summary_plugin.get_page_summary(WikipediaPageRequest(title="Ada Lovelace"))


def test_normalize_search_results_and_page_summary_helpers_cover_skips_limits_and_urls(
    tmp_path: Path,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(WikipediaResearchPluginError, match="missing query payload"):
        wikipedia_service.WikipediaResearchPlugin._normalize_search_results(
            {},
            language="en",
            limit=1,
        )
    with pytest.raises(WikipediaResearchPluginError, match="must be a list"):
        wikipedia_service.WikipediaResearchPlugin._normalize_search_results(
            {"query": {"search": {}}},
            language="en",
            limit=1,
        )

    results = wikipedia_service.WikipediaResearchPlugin._normalize_search_results(
        {
            "query": {
                "search": [
                    "skip",
                    {"title": "Ada Lovelace"},
                    {"title": "Ada Lovelace", "pageid": 123, "snippet": 99},
                    {"title": "Grace Hopper", "pageid": 456, "snippet": "Computer scientist"},
                ]
            }
        },
        language="en",
        limit=1,
    )

    assert len(results) == 1
    assert results[0].title == "Ada Lovelace"
    assert results[0].snippet == ""
    assert "%20" not in str(results[0].url)
    assert wikipedia_service.WikipediaResearchPlugin._summary_url(
        plugin,
        "en",
        "Ada Lovelace/Analytical Engine",
    ).endswith("Ada_Lovelace%2FAnalytical_Engine")

    with pytest.raises(WikipediaResearchPluginError, match="required fields"):
        wikipedia_service.WikipediaResearchPlugin._normalize_page_summary(
            {"title": "Ada"},
            language="en",
            max_extract_chars=10,
        )
    with pytest.raises(WikipediaResearchPluginError, match="canonical page URL"):
        wikipedia_service.WikipediaResearchPlugin._normalize_page_summary(
            {
                "title": "Ada",
                "extract": "summary",
                "content_urls": {"desktop": {}},
            },
            language="en",
            max_extract_chars=10,
        )

    normalized = wikipedia_service.WikipediaResearchPlugin._normalize_page_summary(
        {
            "title": "Ada Lovelace",
            "pageid": "bad",
            "revision": "bad",
            "timestamp": 123,
            "extract": "abcdefghijk",
            "content_urls": {
                "desktop": {"page": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
                "mobile": ["skip"],
            },
        },
        language="en",
        max_extract_chars=5,
    )

    assert normalized["summary"] == "abcde"
    assert normalized["page_id"] is None
    assert normalized["revision"] is None
    assert normalized["last_modified"] is None


def test_page_summary_clamps_requested_extract_size(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "title": "Ada Lovelace",
                "pageid": 1,
                "revision": 2,
                "timestamp": "2026-01-01T00:00:00Z",
                "extract": "x" * 500,
                "content_urls": {
                    "desktop": {"page": "https://en.wikipedia.org/wiki/Ada_Lovelace"}
                },
            },
        )

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.get_page_summary(
        WikipediaPageRequest(title="Ada Lovelace", max_extract_chars=500)
    )

    assert len(result.summary) == 120
