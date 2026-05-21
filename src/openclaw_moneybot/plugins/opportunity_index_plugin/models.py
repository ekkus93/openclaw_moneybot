"""Models for the local opportunity index."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import OpportunitySimilarity


class OpportunityIndexEntry(MoneyBotModel):
    """One indexed opportunity summary."""

    opportunity_id: str
    title: str
    normalized_source_url: str
    counterparty: str | None = None
    tags: list[str] = Field(default_factory=list)
    reward_range: str | None = None
    source_hash: str
    rules_snapshot_ids: list[str] = Field(default_factory=list)
    rule_hashes: list[str] = Field(default_factory=list)
    outcome_labels: list[str] = Field(default_factory=list)
    review_summary: str | None = None


class OpportunityIndexRefreshResult(MoneyBotModel):
    """Result of rebuilding or updating the local opportunity index."""

    entry_count: int = Field(ge=0)
    ledger_record: LedgerRecord


class OpportunitySimilarityQueryRequest(MoneyBotModel):
    """Bounded duplicate and similarity query request."""

    title: str | None = None
    source_url: str | None = None
    counterparty: str | None = None
    payout_usd: float | None = Field(default=None, ge=0)
    limit: int = Field(default=5, ge=1)

    @field_validator("title", "source_url", "counterparty")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_query_shape(self) -> OpportunitySimilarityQueryRequest:
        if self.title is None and self.source_url is None and self.counterparty is None:
            msg = "At least one query field is required."
            raise ValueError(msg)
        return self


class OpportunitySimilarityMatch(MoneyBotModel):
    """One similarity match explanation."""

    opportunity_id: str
    similarity: OpportunitySimilarity
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class OpportunitySimilarityQueryResult(MoneyBotModel):
    """Bounded query result for similar opportunities."""

    index_query_id: str
    matches: list[OpportunitySimilarityMatch] = Field(default_factory=list)
    ledger_record: LedgerRecord
