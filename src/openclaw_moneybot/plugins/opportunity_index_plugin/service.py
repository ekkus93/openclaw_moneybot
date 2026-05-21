"""Bounded local opportunity indexing."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from hashlib import sha256
from urllib.parse import urlparse

from openclaw_moneybot.plugins.opportunity_index_plugin.models import (
    OpportunityIndexEntry,
    OpportunityIndexRefreshResult,
    OpportunitySimilarityMatch,
    OpportunitySimilarityQueryRequest,
    OpportunitySimilarityQueryResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult
from openclaw_moneybot.shared import OpportunityIndexConfig
from openclaw_moneybot.shared.types import OpportunitySimilarity, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.support import record_structured_result
from openclaw_moneybot.utils.ids import make_id


class OpportunityIndexPlugin:
    """Maintain a bounded local index for duplicate and history queries."""

    def __init__(
        self,
        config: OpportunityIndexConfig,
        ledger_service: LedgerService,
    ) -> None:
        self.config = config
        self.ledger_service = ledger_service

    def health(self) -> PluginHealthResult:
        return PluginHealthResult(
            plugin_name="opportunity_index_plugin",
            enabled=self.config.enabled,
            read_only=True,
        )

    def rebuild_index(self) -> OpportunityIndexRefreshResult:
        """Rebuild the bounded local index from ledger state."""

        entries = [
            self._build_entry(opportunity.opportunity_id)
            for opportunity in self.ledger_service.list_opportunities()
        ]
        serialized = [entry.model_dump(mode="json") for entry in entries]
        self._write_index(serialized)
        refresh_id = make_id("opportunity_index")
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=refresh_id,
            record_type=RecordType.OPPORTUNITY_INDEX,
            related_record_id=refresh_id,
            payload={"entry_count": len(entries), "entries": serialized},
        )
        return OpportunityIndexRefreshResult(entry_count=len(entries), ledger_record=ledger_record)

    def update_opportunity(self, opportunity_id: str) -> OpportunityIndexRefreshResult:
        """Incrementally update one indexed opportunity."""

        current = self._load_entries()
        next_entries = [entry for entry in current if entry.opportunity_id != opportunity_id]
        next_entries.append(self._build_entry(opportunity_id))
        next_entries.sort(key=lambda entry: entry.opportunity_id)
        self._write_index([entry.model_dump(mode="json") for entry in next_entries])
        refresh_id = make_id("opportunity_index")
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=refresh_id,
            record_type=RecordType.OPPORTUNITY_INDEX,
            related_record_id=opportunity_id,
            payload={"entry_count": len(next_entries), "updated_opportunity_id": opportunity_id},
        )
        return OpportunityIndexRefreshResult(
            entry_count=len(next_entries),
            ledger_record=ledger_record,
        )

    def query_similar(
        self,
        request: OpportunitySimilarityQueryRequest,
    ) -> OpportunitySimilarityQueryResult:
        """Return bounded similarity matches without exposing raw SQL."""

        if request.limit > self.config.max_results:
            msg = "Requested result limit exceeds the configured maximum."
            raise ValueError(msg)
        entries = self._load_entries()
        if not entries:
            self.rebuild_index()
            entries = self._load_entries()
        matches: list[OpportunitySimilarityMatch] = []
        normalized_title = _normalize(request.title)
        normalized_source_url = _normalize_url(request.source_url)
        normalized_counterparty = _normalize(request.counterparty)
        for entry in entries:
            score, reasons = self._score_entry(
                entry,
                normalized_title=normalized_title,
                normalized_source_url=normalized_source_url,
                normalized_counterparty=normalized_counterparty,
            )
            if score < 0.6:
                continue
            matches.append(
                OpportunitySimilarityMatch(
                    opportunity_id=entry.opportunity_id,
                    similarity=_similarity_bucket(score),
                    score=score,
                    reasons=reasons,
                )
            )
        matches.sort(key=lambda item: (-item.score, item.opportunity_id))
        query_id = make_id("opportunity_index")
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=query_id,
            record_type=RecordType.OPPORTUNITY_INDEX,
            related_record_id=query_id,
            payload={
                "query": request.model_dump(mode="json"),
                "match_ids": [item.opportunity_id for item in matches[: request.limit]],
            },
        )
        return OpportunitySimilarityQueryResult(
            index_query_id=query_id,
            matches=matches[: request.limit],
            ledger_record=ledger_record,
        )

    def _build_entry(self, opportunity_id: str) -> OpportunityIndexEntry:
        opportunity = self.ledger_service.get_opportunity(opportunity_id)
        if opportunity is None:
            msg = f"Unknown opportunity: {opportunity_id}"
            raise ValueError(msg)
        rules_snapshot_ids: list[str] = []
        rule_hashes: list[str] = []
        for event in self.ledger_service.get_related_events(related_type=RecordType.RULE_SNAPSHOT):
            payload = event.payload.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("opportunity_id") != opportunity_id:
                continue
            if isinstance(event.payload.get("record_id"), str):
                rules_snapshot_ids.append(str(event.payload["record_id"]))
            normalized_hash = payload.get("normalized_hash")
            if isinstance(normalized_hash, str):
                rule_hashes.append(normalized_hash)
        outcome_labels: list[str] = []
        review_summary: str | None = None
        for event in self.ledger_service.get_related_events(
            related_type=RecordType.EXPERIMENT_REVIEW
        ):
            if event.payload.get("opportunity_id") != opportunity_id:
                continue
            decision = event.payload.get("decision")
            if isinstance(decision, str):
                outcome_labels.append(decision)
            summary = event.payload.get("summary")
            if isinstance(summary, str):
                review_summary = summary
        normalized_source_url = _normalize_url(str(opportunity.source_url))
        tags = [opportunity.category]
        raw_tags = opportunity.raw_json.get("tags")
        if isinstance(raw_tags, list):
            tags.extend(str(item) for item in raw_tags)
        return OpportunityIndexEntry(
            opportunity_id=opportunity.opportunity_id,
            title=opportunity.name,
            normalized_source_url=normalized_source_url,
            counterparty=None,
            tags=sorted(set(tags)),
            reward_range=_reward_range(opportunity.estimated_revenue_usd),
            source_hash=sha256(normalized_source_url.encode("utf-8")).hexdigest(),
            rules_snapshot_ids=rules_snapshot_ids,
            rule_hashes=rule_hashes,
            outcome_labels=outcome_labels,
            review_summary=review_summary,
        )

    def _load_entries(self) -> list[OpportunityIndexEntry]:
        path = self.config.index_path
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            msg = "Opportunity index payload is malformed."
            raise ValueError(msg)
        return [OpportunityIndexEntry.model_validate(item) for item in payload]

    def _write_index(self, payload: list[dict[str, object]]) -> None:
        path = self.config.index_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _score_entry(
        entry: OpportunityIndexEntry,
        *,
        normalized_title: str,
        normalized_source_url: str,
        normalized_counterparty: str,
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        if normalized_source_url and entry.normalized_source_url == normalized_source_url:
            reasons.append("exact_source_url")
            score = max(score, 1.0)
        if normalized_title:
            title_score = SequenceMatcher(None, normalized_title, _normalize(entry.title)).ratio()
            if title_score >= 0.95:
                reasons.append("near_exact_title")
            elif title_score >= 0.8:
                reasons.append("similar_title")
            score = max(score, title_score)
        if normalized_counterparty and _normalize(entry.counterparty) == normalized_counterparty:
            reasons.append("counterparty_match")
            score = max(score, 0.75)
        return score, reasons


def _normalize(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.lower().split())


def _normalize_url(value: str | None) -> str:
    if value is None:
        return ""
    parsed = urlparse(value)
    normalized_host = (parsed.netloc or "").lower()
    normalized_path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{normalized_host}{normalized_path}".strip()


def _reward_range(value: float | None) -> str | None:
    if value is None:
        return None
    if value < 25:
        return "under_25"
    if value < 100:
        return "25_to_99"
    return "100_plus"


def _similarity_bucket(score: float) -> OpportunitySimilarity:
    if score >= 0.99:
        return OpportunitySimilarity.EXACT
    if score >= 0.85:
        return OpportunitySimilarity.HIGH
    if score >= 0.6:
        return OpportunitySimilarity.MEDIUM
    return OpportunitySimilarity.LOW
