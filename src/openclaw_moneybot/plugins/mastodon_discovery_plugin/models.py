"""Models for bounded Mastodon discovery."""

from __future__ import annotations

from pydantic import Field, HttpUrl, JsonValue, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord


class MastodonPublicTimelineRequest(MoneyBotModel):
    """One bounded Mastodon public timeline sampling request."""

    limit: int = Field(default=10, gt=0, le=40)
    local: bool = False
    remote: bool = False
    only_media: bool = False

    @model_validator(mode="after")
    def validate_scope(self) -> MastodonPublicTimelineRequest:
        if self.local and self.remote:
            msg = "local and remote cannot both be true."
            raise ValueError(msg)
        return self


class MastodonStatusSample(MoneyBotModel):
    """One normalized sampled Mastodon status."""

    status_id: str
    url: HttpUrl | None = None
    created_at: str
    author_handle: str
    author_display_name: str | None = None
    boosted_by_handle: str | None = None
    content_html: str
    content_text: str
    tags: list[str] = Field(default_factory=list)
    links: list[HttpUrl] = Field(default_factory=list)
    visibility: str | None = None
    language: str | None = None
    reply_count: int = Field(default=0, ge=0)
    reblog_count: int = Field(default=0, ge=0)
    favourite_count: int = Field(default=0, ge=0)
    media_attachment_count: int = Field(default=0, ge=0)
    is_sensitive: bool = False
    is_boost: bool = False


class MastodonTimelineSampleResult(MoneyBotModel):
    """Normalized Mastodon public timeline sample."""

    sample_id: str
    instance_base_url: HttpUrl
    result_count: int = Field(ge=0)
    local: bool
    remote: bool
    only_media: bool
    authenticated_request: bool
    statuses: list[MastodonStatusSample] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    ledger_record: LedgerRecord
