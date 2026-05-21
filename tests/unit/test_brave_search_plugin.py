"""Unit tests for the Brave Search plugin."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pytest import MonkeyPatch

from openclaw_moneybot.plugins.brave_search_plugin import (
    BraveSearchPlugin,
    BraveSearchPluginError,
    BraveSearchRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, BraveSearchConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(
    tmp_path: Path,
    *,
    enabled: bool = True,
    handler: httpx.BaseTransport | None = None,
) -> tuple[BraveSearchPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = BraveSearchPlugin(
        BraveSearchConfig(enabled=enabled, max_results=5),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def test_health_reports_missing_api_key(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    plugin, _ = make_plugin(tmp_path)

    health = plugin.health()

    assert health.plugin_name == "brave_search_plugin"
    assert health.status == "missing_api_key"


def test_search_returns_bounded_normalized_results(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "python jobs"
        assert request.headers["X-Subscription-Token"] == "token"
        return httpx.Response(
            200,
            json={
                "web": {
                    "total": 2,
                    "results": [
                        {
                            "title": "Result One",
                            "url": "https://example.com/one",
                            "description": "First result",
                            "age": "2026-01-01",
                            "language": "en",
                            "family_friendly": True,
                        },
                        {
                            "title": "Result Two",
                            "url": "https://example.com/two",
                            "description": "Second result",
                        },
                    ],
                }
            },
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.search(BraveSearchRequest(query="python jobs", count=2))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.WEB_SEARCH,
        related_id=result.search_id,
    )

    assert result.query == "python jobs"
    assert result.result_count == 2
    assert [item.title for item in result.results] == ["Result One", "Result Two"]
    assert result.raw_response_summary["reported_total"] == 2
    assert len(result.evidence_archive_ids) == 1
    assert len(evidence) == 1
    assert evidence[0].evidence_type == "brave_search_response"


def test_search_rejects_when_plugin_disabled(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "token")
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.search(BraveSearchRequest(query="python jobs"))


def test_search_requires_api_key(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(BraveSearchPluginError, match="BRAVE_SEARCH_API_KEY"):
        plugin.search(BraveSearchRequest(query="python jobs"))


def test_search_rejects_requests_above_configured_maximum(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "token")
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="configured maximum"):
        plugin.search(BraveSearchRequest(query="python jobs", count=6))


def test_search_surfaces_transport_failures_as_plugin_errors(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "token")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BraveSearchPluginError, match="unavailable"):
        plugin.search(BraveSearchRequest(query="python jobs"))


def test_search_rejects_malformed_payloads(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"web": {"results": "bad"}})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BraveSearchPluginError, match="results must be a list"):
        plugin.search(BraveSearchRequest(query="python jobs"))
