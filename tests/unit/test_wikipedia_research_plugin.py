"""Unit tests for the Wikipedia research plugin."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

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
