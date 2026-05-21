"""Unit tests for the Mastodon discovery plugin."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from openclaw_moneybot.plugins.mastodon_discovery_plugin import (
    MastodonDiscoveryPlugin,
    MastodonDiscoveryPluginError,
    MastodonPublicTimelineRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, MastodonDiscoveryConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(
    tmp_path: Path,
    *,
    enabled: bool = True,
    require_auth: bool = False,
    handler: httpx.BaseTransport | None = None,
) -> tuple[MastodonDiscoveryPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = MastodonDiscoveryPlugin(
        MastodonDiscoveryConfig(
            enabled=enabled,
            require_auth=require_auth,
            max_results=10,
            api_base_url="https://mastodon.social",
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def test_sample_public_timeline_returns_bounded_normalized_statuses(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "mastodon.social"
        assert request.url.path == "/api/v1/timelines/public"
        assert request.url.params["limit"] == "1"
        assert request.url.params["local"] == "true"
        assert "Authorization" not in request.headers
        return httpx.Response(
            200,
            json=[
                {
                    "id": "100",
                    "url": "https://mastodon.social/@alice/100",
                    "created_at": "2026-05-21T21:00:00Z",
                    "content": "<p>Hello <a href=\"https://example.com/news\">news</a> #AI</p>",
                    "visibility": "public",
                    "language": "en",
                    "replies_count": 1,
                    "reblogs_count": 2,
                    "favourites_count": 3,
                    "media_attachments": [],
                    "sensitive": False,
                    "account": {
                        "acct": "alice",
                        "display_name": "Alice Example",
                    },
                    "tags": [{"name": "AI"}],
                }
            ],
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.sample_public_timeline(
        MastodonPublicTimelineRequest(limit=1, local=True)
    )
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.MASTODON_DISCOVERY,
        related_id=result.sample_id,
    )

    assert result.result_count == 1
    assert result.authenticated_request is False
    assert result.statuses[0].author_handle == "alice"
    assert result.statuses[0].content_text == "Hello news #AI"
    assert result.statuses[0].tags == ["ai"]
    assert str(result.statuses[0].links[0]) == "https://mastodon.social/@alice/100"
    assert evidence[0].evidence_type == "mastodon_public_timeline_response"


def test_sample_public_timeline_uses_optional_auth_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MASTODON_API_TOKEN", "token-123")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer token-123"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "101",
                    "url": "https://mastodon.social/@bob/101",
                    "created_at": "2026-05-21T21:00:00Z",
                    "content": "<p>boost wrapper</p>",
                    "visibility": "public",
                    "language": "en",
                    "replies_count": 0,
                    "reblogs_count": 0,
                    "favourites_count": 0,
                    "media_attachments": [],
                    "sensitive": False,
                    "account": {"acct": "booster", "display_name": "Booster"},
                    "tags": [],
                    "reblog": {
                        "id": "202",
                        "url": "https://mastodon.social/@bob/202",
                        "created_at": "2026-05-21T20:59:00Z",
                        "content": "<p>Original post</p>",
                        "visibility": "public",
                        "language": "en",
                        "replies_count": 4,
                        "reblogs_count": 5,
                        "favourites_count": 6,
                        "media_attachments": [],
                        "sensitive": False,
                        "account": {"acct": "bob@example.social", "display_name": "Bob"},
                        "tags": [],
                    },
                }
            ],
        )

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.sample_public_timeline(MastodonPublicTimelineRequest(limit=1))

    assert result.authenticated_request is True
    assert result.statuses[0].is_boost is True
    assert result.statuses[0].boosted_by_handle == "booster"
    assert result.statuses[0].author_handle == "bob@example.social"


def test_sample_public_timeline_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.sample_public_timeline(MastodonPublicTimelineRequest())


def test_sample_public_timeline_rejects_when_auth_required_but_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MASTODON_API_TOKEN", raising=False)
    plugin, _ = make_plugin(tmp_path, require_auth=True)

    with pytest.raises(MastodonDiscoveryPluginError, match="MASTODON_API_TOKEN"):
        plugin.sample_public_timeline(MastodonPublicTimelineRequest())


def test_sample_public_timeline_rejects_malformed_payloads(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(MastodonDiscoveryPluginError, match="JSON array"):
        plugin.sample_public_timeline(MastodonPublicTimelineRequest())


def test_sample_public_timeline_surfaces_transport_failures_as_plugin_errors(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(MastodonDiscoveryPluginError, match="unavailable"):
        plugin.sample_public_timeline(MastodonPublicTimelineRequest())
