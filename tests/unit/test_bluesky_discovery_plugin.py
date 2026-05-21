"""Unit tests for the Bluesky discovery plugin."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from openclaw_moneybot.plugins.bluesky_discovery_plugin import (
    BlueskyDiscoveryPlugin,
    BlueskyDiscoveryPluginError,
    BlueskyFeedSampleRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, BlueskyDiscoveryConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(
    tmp_path: Path,
    *,
    enabled: bool = True,
    default_feed_uri: str = "",
    handler: httpx.BaseTransport | None = None,
) -> tuple[BlueskyDiscoveryPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = BlueskyDiscoveryPlugin(
        BlueskyDiscoveryConfig(
            enabled=enabled,
            default_feed_uri=default_feed_uri,
            max_results=10,
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def test_sample_feed_returns_bounded_normalized_posts(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "public.api.bsky.app"
        assert request.url.path == "/xrpc/app.bsky.feed.getFeed"
        assert request.url.params["feed"] == "at://did:plc:feed/app.bsky.feed.generator/whats-hot"
        assert request.url.params["limit"] == "1"
        return httpx.Response(
            200,
            json={
                "cursor": "cursor-1",
                "feed": [
                    {
                        "post": {
                            "uri": "at://did:plc:alice/app.bsky.feed.post/3kxyz",
                            "cid": "cid-1",
                            "indexedAt": "2026-05-21T22:00:00Z",
                            "author": {
                                "did": "did:plc:alice",
                                "handle": "alice.bsky.social",
                                "displayName": "Alice Example",
                            },
                            "record": {
                                "text": "Hello Bluesky",
                                "createdAt": "2026-05-21T21:59:00Z",
                                "langs": ["en"],
                                "facets": [
                                    {
                                        "features": [
                                            {"uri": "https://example.com/story"}
                                        ]
                                    }
                                ],
                            },
                            "replyCount": 1,
                            "repostCount": 2,
                            "likeCount": 3,
                            "quoteCount": 4,
                            "labels": [{"val": "news"}],
                            "embed": {"$type": "app.bsky.embed.images#view"},
                        },
                        "reason": {"$type": "app.bsky.feed.defs#reasonRepost"},
                    }
                ],
            },
        )

    plugin, ledger_service = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    result = plugin.sample_feed(
        BlueskyFeedSampleRequest(
            feed_uri="at://did:plc:feed/app.bsky.feed.generator/whats-hot",
            limit=1,
        )
    )
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.BLUESKY_DISCOVERY,
        related_id=result.sample_id,
    )

    assert result.result_count == 1
    assert result.cursor == "cursor-1"
    assert result.posts[0].author_handle == "alice.bsky.social"
    assert str(result.posts[0].post_url) == "https://bsky.app/profile/alice.bsky.social/post/3kxyz"
    assert [str(link) for link in result.posts[0].links] == ["https://example.com/story"]
    assert result.posts[0].labels == ["news"]
    assert result.posts[0].has_media_embed is True
    assert evidence[0].evidence_type == "bluesky_feed_response"


def test_sample_feed_uses_default_feed_uri_when_request_omits_one(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["feed"] == "at://did:plc:feed/app.bsky.feed.generator/default"
        return httpx.Response(200, json={"feed": []})

    plugin, _ = make_plugin(
        tmp_path,
        default_feed_uri="at://did:plc:feed/app.bsky.feed.generator/default",
        handler=httpx.MockTransport(handler),
    )

    result = plugin.sample_feed(BlueskyFeedSampleRequest(limit=1))

    assert result.feed_uri == "at://did:plc:feed/app.bsky.feed.generator/default"
    assert result.result_count == 0


def test_sample_feed_rejects_when_plugin_disabled(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path, enabled=False)

    with pytest.raises(ValueError, match="disabled"):
        plugin.sample_feed(
            BlueskyFeedSampleRequest(
                feed_uri="at://did:plc:feed/app.bsky.feed.generator/whats-hot",
                limit=1,
            )
        )


def test_sample_feed_rejects_without_any_feed_uri(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(BlueskyDiscoveryPluginError, match="default_feed_uri"):
        plugin.sample_feed(BlueskyFeedSampleRequest(limit=1))


def test_sample_feed_rejects_malformed_payloads(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"cursor": "x"})

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BlueskyDiscoveryPluginError, match="feed list"):
        plugin.sample_feed(
            BlueskyFeedSampleRequest(
                feed_uri="at://did:plc:feed/app.bsky.feed.generator/whats-hot",
                limit=1,
            )
        )


def test_sample_feed_surfaces_transport_failures_as_plugin_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin, _ = make_plugin(tmp_path, handler=httpx.MockTransport(handler))

    with pytest.raises(BlueskyDiscoveryPluginError, match="unavailable"):
        plugin.sample_feed(
            BlueskyFeedSampleRequest(
                feed_uri="at://did:plc:feed/app.bsky.feed.generator/whats-hot",
                limit=1,
            )
        )
