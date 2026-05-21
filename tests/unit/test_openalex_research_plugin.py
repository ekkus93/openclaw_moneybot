"""Unit tests for the OpenAlex research plugin."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from openclaw_moneybot.plugins.openalex_research_plugin import (
    OpenAlexResearchPlugin,
    OpenAlexResearchPluginError,
    OpenAlexSearchRequest,
    OpenAlexWorkRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, OpenAlexResearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(
    tmp_path: Path,
    *,
    enabled: bool = True,
    handler: httpx.BaseTransport | None = None,
) -> tuple[OpenAlexResearchPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = OpenAlexResearchPlugin(
        OpenAlexResearchConfig(enabled=enabled, max_results=5, max_abstract_chars=80),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def test_search_returns_bounded_normalized_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.openalex.org"
        assert request.url.path == "/works"
        assert request.url.params["search"] == "bounded agents"
        assert request.url.params["per_page"] == "1"
        assert request.url.params["page"] == "2"
        assert request.url.params["filter"] == "publication_year:2024,is_oa:true"
        assert request.url.params["api_key"] == "test-key"
        return httpx.Response(
            200,
            json={
                "meta": {"count": 12, "page": 2, "per_page": 1},
                "results": [
                    {
                        "id": "https://openalex.org/W1234567890",
                        "doi": "https://doi.org/10.1000/example",
                        "display_name": "Bounded Agents for Research Automation",
                        "publication_year": 2024,
                        "publication_date": "2024-02-01",
                        "type": "article",
                        "language": "en",
                        "cited_by_count": 11,
                        "open_access": {"is_oa": True, "oa_status": "gold"},
                        "abstract_inverted_index": {
                            "Bounded": [0],
                            "agents": [1],
                            "for": [2],
                            "research": [3],
                            "automation": [4],
                        },
                        "authorships": [
                            {"author": {"display_name": "Ada Lovelace"}},
                            {"author": {"display_name": "Grace Hopper"}},
                        ],
                        "primary_topic": {"display_name": "AI agents"},
                        "topics": [{"display_name": "AI agents"}, {"display_name": "Automation"}],
                        "primary_location": {
                            "landing_page_url": "https://example.org/paper",
                            "pdf_url": "https://example.org/paper.pdf",
                            "source": {"display_name": "Example Journal"},
                        },
                    }
                ],
            },
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.search(
        OpenAlexSearchRequest(
            query="bounded agents",
            count=1,
            page=2,
            publication_year=2024,
            open_access_only=True,
        )
    )
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.OPENALEX_RESEARCH,
        related_id=result.lookup_id,
    )

    assert result.query == "bounded agents"
    assert result.page == 2
    assert result.result_count == 1
    assert result.total_results == 12
    assert result.results[0].title == "Bounded Agents for Research Automation"
    assert result.results[0].authors == ["Ada Lovelace", "Grace Hopper"]
    assert result.results[0].abstract == "Bounded agents for research automation"
    assert result.results[0].primary_topic == "AI agents"
    assert evidence[0].evidence_type == "openalex_search_response"


def test_get_work_returns_normalized_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/works/W1234567890"
        assert request.url.params["api_key"] == "test-key"
        return httpx.Response(
            200,
            json={
                "id": "https://openalex.org/W1234567890",
                "doi": "https://doi.org/10.1000/example",
                "display_name": "Bounded Agents for Research Automation",
                "publication_year": 2024,
                "publication_date": "2024-02-01",
                "type": "article",
                "language": "en",
                "cited_by_count": 11,
                "open_access": {
                    "is_oa": True,
                    "oa_status": "gold",
                    "oa_url": "https://example.org/oa",
                },
                "abstract_inverted_index": {
                    "This": [0],
                    "abstract": [1],
                    "is": [2],
                    "clipped": [3],
                    "for": [4],
                    "tests": [5],
                },
                "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
                "primary_topic": {"display_name": "AI agents"},
                "topics": [{"display_name": "AI agents"}],
                "best_oa_location": {
                    "landing_page_url": "https://example.org/paper",
                    "pdf_url": "https://example.org/paper.pdf",
                    "source": {"display_name": "Example Repository"},
                },
            },
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.get_work(OpenAlexWorkRequest(work_id="https://openalex.org/W1234567890"))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.OPENALEX_RESEARCH,
        related_id=result.lookup_id,
    )

    assert result.work.title == "Bounded Agents for Research Automation"
    assert result.work.source_display_name == "Example Repository"
    assert str(result.work.pdf_url) == "https://example.org/paper.pdf"
    assert result.work.is_open_access is True
    assert evidence[0].evidence_type == "openalex_work_response"


def test_search_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.search(OpenAlexSearchRequest(query="bounded agents"))


def test_search_rejects_when_api_key_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(OpenAlexResearchPluginError, match="OPENALEX_API_KEY"):
        plugin.search(OpenAlexSearchRequest(query="bounded agents"))


def test_get_work_rejects_malformed_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"display_name": "Missing id"})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(OpenAlexResearchPluginError, match="missing id"):
        plugin.get_work(OpenAlexWorkRequest(work_id="W1"))


def test_search_surfaces_transport_failures_as_plugin_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(OpenAlexResearchPluginError, match="unavailable"):
        plugin.search(OpenAlexSearchRequest(query="bounded agents"))
