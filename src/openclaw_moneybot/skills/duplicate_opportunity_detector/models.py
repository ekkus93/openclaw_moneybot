"""Models for duplicate opportunity detection."""

from __future__ import annotations

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import DuplicateConfidence


class OpportunityFingerprint(MoneyBotModel):
    """Normalized subset of opportunity data for duplicate checks."""

    opportunity_id: str
    title: str
    source_url: str
    rules_url: str | None = None
    description: str | None = None
    payout_usd: float | None = Field(default=None, ge=0)
    platform: str | None = None
    deadline: str | None = None


class DuplicateOpportunityDetectorRequest(MoneyBotModel):
    """Request for duplicate-opportunity checks."""

    candidate: OpportunityFingerprint
    existing: list[OpportunityFingerprint] = Field(default_factory=list)


class DuplicateOpportunityDetectorResult(MoneyBotModel):
    """Structured duplicate-opportunity result."""

    duplicate_analysis_id: str
    is_duplicate: bool
    confidence: DuplicateConfidence
    matched_opportunity_ids: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    safe_next_steps: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
