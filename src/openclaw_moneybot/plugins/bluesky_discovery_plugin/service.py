"""Read-only Bluesky discovery integration."""

from __future__ import annotations

import re

import httpx

from openclaw_moneybot.plugins.bluesky_discovery_plugin.models import (
    BlueskyFeedSampleRequest,
    BlueskyFeedSampleResult,
    BlueskyPostSample,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, BlueskyDiscoveryConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id

_AT_URI_RE = re.compile(
    r"^at://(?P<repo>[^/]+)/app\.bsky\.feed\.post/(?P<rkey>[^/?#]+)$"
)


class BlueskyDiscoveryPluginError(RuntimeError):
    """Raised when Bluesky discovery cannot be completed safely."""


class BlueskyDiscoveryPlugin:
    """Sample public Bluesky feeds through the public AppView API."""

    def __init__(
        self,
        config: BlueskyDiscoveryConfig,
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

        status = "ok" if self._default_feed_uri() is not None else "missing_default_feed_uri"
        return PluginHealthResult(
            plugin_name="bluesky_discovery_plugin",
            enabled=self.config.enabled,
            read_only=True,
            status=status,
        )

    def sample_feed(self, request: BlueskyFeedSampleRequest) -> BlueskyFeedSampleResult:
        """Sample one bounded Bluesky feed page."""

        if not self.config.enabled:
            msg = "bluesky_discovery_plugin is disabled."
            raise ValueError(msg)
        if request.limit > self.config.max_results:
            msg = "Requested result count exceeds the configured maximum."
            raise ValueError(msg)
        feed_uri = request.feed_uri or self._default_feed_uri()
        if feed_uri is None:
            msg = "No Bluesky feed URI provided and no default_feed_uri is configured."
            raise BlueskyDiscoveryPluginError(msg)

        sample_id = make_id("bluesky")
        try:
            response = self._client.get(
                self._feed_url(),
                params={
                    "feed": feed_uri,
                    "limit": request.limit,
                    **({} if request.cursor is None else {"cursor": request.cursor}),
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(sample_id, "bluesky_feed_failed", reason="transport_error")
            msg = "Bluesky feed sampling is unavailable."
            raise BlueskyDiscoveryPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            self._record_failure(sample_id, "bluesky_feed_failed", reason="invalid_response")
            msg = f"Bluesky feed sampling request failed: {error}"
            raise BlueskyDiscoveryPluginError(msg) from error

        if not isinstance(payload, dict):
            msg = "Bluesky feed response must be a JSON object."
            raise BlueskyDiscoveryPluginError(msg)
        posts, cursor = self._normalize_feed(payload, limit=request.limit)
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.BLUESKY_DISCOVERY,
            related_id=sample_id,
            evidence_type="bluesky_feed_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded Bluesky feed response snapshot",
        )
        summary = {
            "api_base_url": self.config.api_base_url,
            "feed_uri": feed_uri,
            "cursor": cursor,
            "post_uris": [item.post_uri for item in posts],
            "author_handles": [item.author_handle for item in posts],
            "links": sorted({str(link) for item in posts for link in item.links}),
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=sample_id,
            record_type=RecordType.BLUESKY_DISCOVERY,
            related_record_id=sample_id,
            payload={
                "mode": "feed_sample",
                "api_base_url": self.config.api_base_url,
                "feed_uri": feed_uri,
                "result_count": len(posts),
                "cursor": cursor,
                "post_uris": [item.post_uri for item in posts],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return BlueskyFeedSampleResult(
            sample_id=sample_id,
            api_base_url=self.config.api_base_url,
            feed_uri=feed_uri,
            result_count=len(posts),
            cursor=cursor,
            posts=posts,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def _default_feed_uri(self) -> str | None:
        value = self.config.default_feed_uri.strip()
        return None if value == "" else value

    def _feed_url(self) -> str:
        return f"{self.config.api_base_url.rstrip('/')}/xrpc/app.bsky.feed.getFeed"

    def _record_failure(self, sample_id: str, event_name: str, **payload: object) -> None:
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=sample_id,
            event_name=event_name,
            payload=payload,
        )

    def _normalize_feed(
        self,
        payload: dict[str, object],
        *,
        limit: int,
    ) -> tuple[list[BlueskyPostSample], str | None]:
        raw_feed = payload.get("feed")
        if not isinstance(raw_feed, list):
            msg = "Bluesky feed response missing feed list."
            raise BlueskyDiscoveryPluginError(msg)
        posts: list[BlueskyPostSample] = []
        for item in raw_feed:
            if len(posts) >= limit:
                break
            if not isinstance(item, dict):
                continue
            posts.append(self._normalize_feed_item(item))
        cursor = payload.get("cursor")
        if not isinstance(cursor, str):
            cursor = None
        return posts, cursor

    def _normalize_feed_item(self, payload: dict[str, object]) -> BlueskyPostSample:
        post = payload.get("post")
        if not isinstance(post, dict):
            msg = "Bluesky feed item is missing post payload."
            raise BlueskyDiscoveryPluginError(msg)
        post_uri = post.get("uri")
        cid = post.get("cid")
        indexed_at = post.get("indexedAt")
        author = post.get("author")
        record = post.get("record")
        if not isinstance(post_uri, str):
            msg = "Bluesky post is missing uri."
            raise BlueskyDiscoveryPluginError(msg)
        if not isinstance(cid, str):
            msg = "Bluesky post is missing cid."
            raise BlueskyDiscoveryPluginError(msg)
        if not isinstance(indexed_at, str):
            msg = "Bluesky post is missing indexedAt."
            raise BlueskyDiscoveryPluginError(msg)
        if not isinstance(author, dict):
            msg = "Bluesky post is missing author."
            raise BlueskyDiscoveryPluginError(msg)
        if not isinstance(record, dict):
            msg = "Bluesky post is missing record."
            raise BlueskyDiscoveryPluginError(msg)
        author_did = author.get("did")
        author_handle = author.get("handle")
        text = record.get("text")
        if not isinstance(author_did, str):
            msg = "Bluesky post author is missing did."
            raise BlueskyDiscoveryPluginError(msg)
        if not isinstance(author_handle, str):
            msg = "Bluesky post author is missing handle."
            raise BlueskyDiscoveryPluginError(msg)
        if not isinstance(text, str):
            msg = "Bluesky post record is missing text."
            raise BlueskyDiscoveryPluginError(msg)
        return BlueskyPostSample(
            post_uri=post_uri,
            post_url=self._post_url(post_uri=post_uri, handle=author_handle),
            cid=cid,
            indexed_at=indexed_at,
            created_at=self._optional_string(record.get("createdAt")),
            author_did=author_did,
            author_handle=author_handle,
            author_display_name=self._optional_string(author.get("displayName")),
            text=text,
            langs=self._string_list(record.get("langs")),
            reply_count=self._int_or_zero(post.get("replyCount")),
            repost_count=self._int_or_zero(post.get("repostCount")),
            like_count=self._int_or_zero(post.get("likeCount")),
            quote_count=self._int_or_zero(post.get("quoteCount")),
            labels=self._labels(post.get("labels")),
            links=self._links(record.get("facets")),
            has_media_embed=self._has_media_embed(post.get("embed")),
            is_reply=isinstance(record.get("reply"), dict),
            feed_reason=self._feed_reason(payload.get("reason")),
        )

    @staticmethod
    def _post_url(*, post_uri: str, handle: str) -> str | None:
        match = _AT_URI_RE.match(post_uri)
        if match is None:
            return None
        rkey = match.group("rkey")
        return f"https://bsky.app/profile/{handle}/post/{rkey}"

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return None if normalized == "" else normalized

    @staticmethod
    def _int_or_zero(value: object) -> int:
        return value if isinstance(value, int) else 0

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]

    @staticmethod
    def _labels(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        labels: list[str] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            val = item.get("val")
            if isinstance(val, str) and val:
                labels.append(val)
        return labels

    @staticmethod
    def _links(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        links: list[str] = []
        seen: set[str] = set()
        for facet in value:
            if not isinstance(facet, dict):
                continue
            features = facet.get("features")
            if not isinstance(features, list):
                continue
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                uri = feature.get("uri")
                if isinstance(uri, str) and uri not in seen and uri:
                    seen.add(uri)
                    links.append(uri)
        return links

    @staticmethod
    def _has_media_embed(value: object) -> bool:
        if not isinstance(value, dict):
            return False
        embed_type = value.get("$type")
        if not isinstance(embed_type, str):
            return False
        return "images" in embed_type or "video" in embed_type or "external" in embed_type

    @staticmethod
    def _feed_reason(value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        reason_type = value.get("$type")
        if not isinstance(reason_type, str):
            return None
        return reason_type
