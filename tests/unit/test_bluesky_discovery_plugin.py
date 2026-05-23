"""Unit tests for the Bluesky discovery plugin."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

import openclaw_moneybot.plugins.bluesky_discovery_plugin.service as bluesky_service
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


def audit_event_payloads(ledger_service: LedgerService) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for event in ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT):
        payload = event.payload.get("payload")
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


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


def test_health_reports_missing_default_feed_uri_and_limit_is_bounded(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    assert plugin.health().status == "missing_default_feed_uri"
    with pytest.raises(ValueError, match="configured maximum"):
        plugin.sample_feed(
            BlueskyFeedSampleRequest(
                feed_uri="at://did:plc:feed/app.bsky.feed.generator/whats-hot",
                limit=11,
            )
        )


@pytest.mark.parametrize(
    ("handler", "match_text"),
    [
        (lambda request: httpx.Response(500), "request failed"),
        (lambda request: httpx.Response(200, text="{bad-json}"), "request failed"),
    ],
)
def test_sample_feed_records_failures_for_invalid_responses(
    tmp_path: Path,
    handler: Callable[[httpx.Request], httpx.Response],
    match_text: str,
) -> None:
    plugin, ledger_service = make_plugin(
        tmp_path,
        handler=httpx.MockTransport(handler),
    )

    with pytest.raises(BlueskyDiscoveryPluginError, match=match_text):
        plugin.sample_feed(
            BlueskyFeedSampleRequest(
                feed_uri="at://did:plc:feed/app.bsky.feed.generator/whats-hot",
                limit=1,
            )
        )

    payloads = audit_event_payloads(ledger_service)
    assert payloads[-1]["event_name"] == "bluesky_feed_failed"


def test_normalize_feed_and_helpers_cover_limits_skips_and_malformed_items(
    tmp_path: Path,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    posts, cursor = plugin._normalize_feed(
        {
            "cursor": 123,
            "feed": [
                "skip-me",
                {
                    "post": {
                        "uri": "at://did:plc:alice/app.bsky.feed.post/3kxyz",
                        "cid": "cid-1",
                        "indexedAt": "2026-05-21T22:00:00Z",
                        "author": {"did": "did:plc:alice", "handle": "alice.bsky.social"},
                        "record": {
                            "text": "Hello",
                            "langs": ["en", 1],
                            "facets": [
                                {"features": [{"uri": "https://example.com/story"}]},
                                {"features": [{"uri": "https://example.com/story"}]},
                                {"features": ["skip"]},
                            ],
                        },
                        "labels": [{"val": "news"}, {"bad": "skip"}, "skip"],
                        "replyCount": "bad",
                        "embed": {"$type": "app.bsky.embed.video#view"},
                    }
                },
                {
                    "post": {
                        "uri": "at://did:plc:bob/app.bsky.feed.post/3kabd",
                        "cid": "cid-2",
                        "indexedAt": "2026-05-21T22:05:00Z",
                        "author": {"did": "did:plc:bob", "handle": "bob.bsky.social"},
                        "record": {"text": "Second post"},
                    }
                },
            ],
        },
        limit=1,
    )

    assert cursor is None
    assert len(posts) == 1
    assert [str(link) for link in posts[0].links] == ["https://example.com/story"]
    assert posts[0].labels == ["news"]
    assert posts[0].langs == ["en"]
    assert posts[0].reply_count == 0
    assert posts[0].has_media_embed is True
    assert bluesky_service.BlueskyDiscoveryPlugin._post_url(
        post_uri="https://example.com/not-at-uri",
        handle="alice.bsky.social",
    ) is None
    assert bluesky_service.BlueskyDiscoveryPlugin._optional_string("  hi  ") == "hi"
    assert bluesky_service.BlueskyDiscoveryPlugin._optional_string("   ") is None
    assert bluesky_service.BlueskyDiscoveryPlugin._feed_reason({"$type": 1}) is None
    assert bluesky_service.BlueskyDiscoveryPlugin._feed_reason("bad") is None


@pytest.mark.parametrize(
    ("payload", "match_text"),
    [
        ({}, "missing post payload"),
        ({"post": {"cid": "cid", "indexedAt": "x", "author": {}, "record": {}}}, "missing uri"),
        (
            {
                "post": {
                    "uri": "at://did:plc:alice/app.bsky.feed.post/1",
                    "indexedAt": "x",
                    "author": {},
                    "record": {},
                }
            },
            "missing cid",
        ),
        (
            {
                "post": {
                    "uri": "at://did:plc:alice/app.bsky.feed.post/1",
                    "cid": "cid",
                    "author": {},
                    "record": {},
                }
            },
            "missing indexedAt",
        ),
        (
            {
                "post": {
                    "uri": "at://did:plc:alice/app.bsky.feed.post/1",
                    "cid": "cid",
                    "indexedAt": "x",
                    "record": {},
                }
            },
            "missing author",
        ),
        (
            {
                "post": {
                    "uri": "at://did:plc:alice/app.bsky.feed.post/1",
                    "cid": "cid",
                    "indexedAt": "x",
                    "author": {},
                    "record": [],
                }
            },
            "missing record",
        ),
        (
            {
                "post": {
                    "uri": "at://did:plc:alice/app.bsky.feed.post/1",
                    "cid": "cid",
                    "indexedAt": "x",
                    "author": {"did": "d", "handle": "h"},
                }
            },
            "missing record",
        ),
        (
            {
                "post": {
                    "uri": "at://did:plc:alice/app.bsky.feed.post/1",
                    "cid": "cid",
                    "indexedAt": "x",
                    "author": {"handle": "h"},
                    "record": {"text": "x"},
                }
            },
            "missing did",
        ),
        (
            {
                "post": {
                    "uri": "at://did:plc:alice/app.bsky.feed.post/1",
                    "cid": "cid",
                    "indexedAt": "x",
                    "author": {"did": "d"},
                    "record": {"text": "x"},
                }
            },
            "missing handle",
        ),
        (
            {
                "post": {
                    "uri": "at://did:plc:alice/app.bsky.feed.post/1",
                    "cid": "cid",
                    "indexedAt": "x",
                    "author": {"did": "d", "handle": "h"},
                    "record": {},
                }
            },
            "missing text",
        ),
    ],
)
def test_normalize_feed_item_rejects_missing_required_fields(
    tmp_path: Path,
    payload: dict[str, object],
    match_text: str,
) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(BlueskyDiscoveryPluginError, match=match_text):
        plugin._normalize_feed_item(payload)
