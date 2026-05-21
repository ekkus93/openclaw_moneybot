"""Read-only Mastodon discovery integration."""

from __future__ import annotations

import os
from html.parser import HTMLParser

import httpx

from openclaw_moneybot.plugins.mastodon_discovery_plugin.models import (
    MastodonPublicTimelineRequest,
    MastodonStatusSample,
    MastodonTimelineSampleResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, MastodonDiscoveryConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.skills.tos_legal_checker.extract import normalize_text
from openclaw_moneybot.utils.ids import make_id


class MastodonDiscoveryPluginError(RuntimeError):
    """Raised when Mastodon discovery cannot be completed safely."""


class MastodonDiscoveryPlugin:
    """Sample public Mastodon timelines through a bounded read-only API."""

    def __init__(
        self,
        config: MastodonDiscoveryConfig,
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
        """Return plugin status, including optional token state."""

        token = self._api_token()
        status = "ok"
        if self.config.require_auth and token is None:
            status = "missing_api_token"
        return PluginHealthResult(
            plugin_name="mastodon_discovery_plugin",
            enabled=self.config.enabled,
            read_only=True,
            status=status,
        )

    def sample_public_timeline(
        self,
        request: MastodonPublicTimelineRequest,
    ) -> MastodonTimelineSampleResult:
        """Sample one bounded Mastodon public timeline page."""

        if not self.config.enabled:
            msg = "mastodon_discovery_plugin is disabled."
            raise ValueError(msg)
        if request.limit > self.config.max_results:
            msg = "Requested result count exceeds the configured maximum."
            raise ValueError(msg)
        api_token = self._api_token()
        if self.config.require_auth and api_token is None:
            msg = f"Missing Mastodon API token in {self.config.api_token_env_var}."
            raise MastodonDiscoveryPluginError(msg)

        sample_id = make_id("mastodon")
        try:
            response = self._client.get(
                self._timeline_url(),
                params={
                    "limit": request.limit,
                    **({"local": "true"} if request.local else {}),
                    **({"remote": "true"} if request.remote else {}),
                    **({"only_media": "true"} if request.only_media else {}),
                },
                headers=self._headers(api_token),
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            self._record_failure(
                sample_id,
                "mastodon_public_timeline_failed",
                reason="transport_error",
            )
            msg = "Mastodon public timeline is unavailable."
            raise MastodonDiscoveryPluginError(msg) from error
        except (httpx.HTTPStatusError, ValueError) as error:
            self._record_failure(
                sample_id,
                "mastodon_public_timeline_failed",
                reason="invalid_response",
            )
            msg = f"Mastodon public timeline request failed: {error}"
            raise MastodonDiscoveryPluginError(msg) from error

        if not isinstance(payload, list):
            msg = "Mastodon public timeline response must be a JSON array."
            raise MastodonDiscoveryPluginError(msg)
        statuses = self._normalize_statuses(payload, limit=request.limit)
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.MASTODON_DISCOVERY,
            related_id=sample_id,
            evidence_type="mastodon_public_timeline_response",
            payload={
                "request": request.model_dump(mode="json"),
                "response": payload,
            },
            notes="Bounded Mastodon public timeline response snapshot",
        )
        summary = {
            "instance_base_url": self.config.api_base_url,
            "local": request.local,
            "remote": request.remote,
            "only_media": request.only_media,
            "authenticated_request": api_token is not None,
            "status_ids": [item.status_id for item in statuses],
            "author_handles": [item.author_handle for item in statuses],
            "tags": sorted({tag for item in statuses for tag in item.tags}),
        }
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=sample_id,
            record_type=RecordType.MASTODON_DISCOVERY,
            related_record_id=sample_id,
            payload={
                "mode": "public_timeline",
                "instance_base_url": self.config.api_base_url,
                "local": request.local,
                "remote": request.remote,
                "only_media": request.only_media,
                "authenticated_request": api_token is not None,
                "result_count": len(statuses),
                "status_ids": [item.status_id for item in statuses],
                "evidence_archive_ids": [evidence_id],
            },
        )
        return MastodonTimelineSampleResult(
            sample_id=sample_id,
            instance_base_url=self.config.api_base_url,
            result_count=len(statuses),
            local=request.local,
            remote=request.remote,
            only_media=request.only_media,
            authenticated_request=api_token is not None,
            statuses=statuses,
            evidence_archive_ids=[evidence_id],
            raw_response_summary=summary,
            ledger_record=ledger_record,
        )

    def _api_token(self) -> str | None:
        token = os.environ.get(self.config.api_token_env_var)
        if token is None:
            return None
        normalized = token.strip()
        return None if normalized == "" else normalized

    def _timeline_url(self) -> str:
        return f"{self.config.api_base_url.rstrip('/')}/api/v1/timelines/public"

    @staticmethod
    def _headers(api_token: str | None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if api_token is not None:
            headers["Authorization"] = f"Bearer {api_token}"
        return headers

    def _record_failure(self, sample_id: str, event_name: str, **payload: object) -> None:
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=sample_id,
            event_name=event_name,
            payload=payload,
        )

    def _normalize_statuses(
        self,
        payload: list[object],
        *,
        limit: int,
    ) -> list[MastodonStatusSample]:
        statuses: list[MastodonStatusSample] = []
        for item in payload:
            if len(statuses) >= limit:
                break
            if not isinstance(item, dict):
                continue
            statuses.append(self._normalize_status(item))
        return statuses

    def _normalize_status(self, payload: dict[str, object]) -> MastodonStatusSample:
        base_payload = payload
        boosted_by_handle: str | None = None
        reblog = payload.get("reblog")
        is_boost = False
        if isinstance(reblog, dict):
            is_boost = True
            base_payload = reblog
            boosted_by_handle = self._account_handle(payload.get("account"))
        status_id = base_payload.get("id")
        created_at = base_payload.get("created_at")
        account = base_payload.get("account")
        content_html = self._string_or_none(base_payload.get("content"))
        if not isinstance(status_id, str):
            msg = "Mastodon status is missing id."
            raise MastodonDiscoveryPluginError(msg)
        if not isinstance(created_at, str):
            msg = "Mastodon status is missing created_at."
            raise MastodonDiscoveryPluginError(msg)
        if content_html is None:
            msg = "Mastodon status is missing content."
            raise MastodonDiscoveryPluginError(msg)

        normalized_links = _extract_links(content_html)
        url = self._string_or_none(base_payload.get("url"))
        if url is not None:
            normalized_links = [url, *normalized_links]
        account_display_name = self._account_display_name(account)
        tags = self._tag_names(base_payload.get("tags"))
        media_attachment_count = self._list_length(base_payload.get("media_attachments"))
        return MastodonStatusSample(
            status_id=status_id,
            url=url,
            created_at=created_at,
            author_handle=self._account_handle(account),
            author_display_name=account_display_name,
            boosted_by_handle=boosted_by_handle,
            content_html=content_html,
            content_text=normalize_text(content_html),
            tags=tags,
            links=normalized_links,
            visibility=self._string_or_none(base_payload.get("visibility")),
            language=self._string_or_none(base_payload.get("language")),
            reply_count=self._int_or_zero(base_payload.get("replies_count")),
            reblog_count=self._int_or_zero(base_payload.get("reblogs_count")),
            favourite_count=self._int_or_zero(base_payload.get("favourites_count")),
            media_attachment_count=media_attachment_count,
            is_sensitive=bool(base_payload.get("sensitive")),
            is_boost=is_boost,
        )

    @staticmethod
    def _account_handle(account: object) -> str:
        if not isinstance(account, dict):
            msg = "Mastodon status is missing account."
            raise MastodonDiscoveryPluginError(msg)
        acct = account.get("acct")
        if not isinstance(acct, str) or not acct.strip():
            msg = "Mastodon status account is missing acct."
            raise MastodonDiscoveryPluginError(msg)
        return acct.strip()

    @staticmethod
    def _account_display_name(account: object) -> str | None:
        if not isinstance(account, dict):
            return None
        display_name = account.get("display_name")
        if not isinstance(display_name, str):
            return None
        normalized = normalize_text(display_name)
        return normalized or None

    @staticmethod
    def _tag_names(tags: object) -> list[str]:
        if not isinstance(tags, list):
            return []
        names: list[str] = []
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            name = tag.get("name")
            if isinstance(name, str):
                normalized = name.strip().lower()
                if normalized:
                    names.append(normalized)
        return names

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _int_or_zero(value: object) -> int:
        return value if isinstance(value, int) else 0

    @staticmethod
    def _list_length(value: object) -> int:
        return len(value) if isinstance(value, list) else 0


class _LinkExtractor(HTMLParser):
    """Extract links from Mastodon HTML content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = next((value for key, value in attrs if key == "href"), None)
        if href is not None and href.strip():
            self.links.append(href.strip())


def _extract_links(content_html: str) -> list[str]:
    parser = _LinkExtractor()
    parser.feed(content_html)
    unique_links: list[str] = []
    seen: set[str] = set()
    for link in parser.links:
        if link in seen:
            continue
        seen.add(link)
        unique_links.append(link)
    return unique_links
