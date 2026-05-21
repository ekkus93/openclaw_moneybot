"""Models for payout reconciliation."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import ReconciliationStatus


class ReconciliationObservation(MoneyBotModel):
    """One observed payout-related fact."""

    observation_id: str
    amount: float = Field(ge=0)
    currency_or_asset: str
    observed_at: datetime
    counterparty: str | None = None
    reference_id: str | None = None
    source_type: str
    evidence_archive_id: str | None = None


class RevenueReconciliationRequest(MoneyBotModel):
    """Request for comparing expected and observed payouts."""

    opportunity_id: str
    expected_amount: float = Field(ge=0)
    currency_or_asset: str
    current_date: datetime
    expected_date: datetime | None = None
    expected_counterparty: str | None = None
    amount_tolerance: float = Field(default=0.01, ge=0)
    observations: list[ReconciliationObservation] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)


class RevenueReconciliationResult(MoneyBotModel):
    """Structured reconciliation outcome."""

    reconciliation_id: str
    status: ReconciliationStatus
    expected_amount: float = Field(ge=0)
    observed_amount: float = Field(ge=0)
    currency_or_asset: str
    variance: float
    matched_artifacts: list[str] = Field(default_factory=list)
    missing_artifacts: list[str] = Field(default_factory=list)
    followup_recommended: bool
    reason_codes: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
