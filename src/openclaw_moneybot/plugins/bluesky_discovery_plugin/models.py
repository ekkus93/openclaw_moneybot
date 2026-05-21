"""Models for bounded Bluesky discovery."""

from __future__ import annotations

from pydantic import Field, HttpUrl, JsonValue, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class BlueskyFeedSampleRequest(MoneyBotModel):
    """One bounded Bluesky feed sampling request."""

    feed_uri: str | None = None
    limit: int = Field(default=10, gt=0, le=100)
    cursor: str | None = Field(default=None, max_length=512)

    @field_validator("feed_uri", "cursor")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return None if normalized == "" else normalized


class BlueskyPostSample(MoneyBotModel):
    """One normalized sampled Bluesky post."""

    post_uri: str
    post_url: HttpUrl | None = None
    cid: str
    indexed_at: str
    created_at: str | None = None
    author_did: str
    author_handle: str
    author_display_name: str | None = None
    text: str
    langs: list[str] = Field(default_factory=list)
    reply_count: int = Field(default=0, ge=0)
    repost_count: int = Field(default=0, ge=0)
    like_count: int = Field(default=0, ge=0)
    quote_count: int = Field(default=0, ge=0)
    labels: list[str] = Field(default_factory=list)
    links: list[HttpUrl] = Field(default_factory=list)
    has_media_embed: bool = False
    is_reply: bool = False
    feed_reason: str | None = None


class BlueskyFeedSampleResult(MoneyBotModel):
    """Normalized Bluesky feed sample."""

    sample_id: str
    api_base_url: HttpUrl
    feed_uri: str
    result_count: int = Field(ge=0)
    cursor: str | None = None
    posts: list[BlueskyPostSample] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
