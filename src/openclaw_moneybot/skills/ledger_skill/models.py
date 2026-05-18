"""Ledger skill models."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from openclaw_moneybot.shared import (
    BudgetPlan,
    EvidenceRecord,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    TosLegalCheck,
    WalletTransactionRecord,
)
from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.types import RecordType


class LedgerWriteResult(MoneyBotModel):
    """Result of a ledger write operation."""

    record_id: str
    ledger_event_id: str
    ledger_write_confirmed: bool = True
    reused_existing_event: bool = False


class LedgerTimelineEntry(MoneyBotModel):
    """An item in the opportunity timeline."""

    created_at: str
    event_type: str
    related_type: RecordType
    related_id: str


class LedgerEventEntry(MoneyBotModel):
    """A generic ledger event entry."""

    ledger_event_id: str
    created_at: str
    event_type: str
    related_type: RecordType
    related_id: str
    payload: dict[str, object]


class TaxExportResult(MoneyBotModel):
    """Result of exporting ledger tax/accounting data."""

    output_path: Path
    row_count: int = Field(ge=0)


class SpendAuthorizationBundle(MoneyBotModel):
    """Ledger-backed authorization context for a spend request."""

    spend_request: SpendRequest
    opportunity: Opportunity | None = None
    policy_decision: PolicyDecision | None = None
    budget_plan: BudgetPlan | None = None
    tos_legal_check: TosLegalCheck | None = None
    evidence_records: list[EvidenceRecord] = Field(default_factory=list)
    prior_wallet_transactions: list[WalletTransactionRecord] = Field(default_factory=list)
    ledger_record_exists: bool = False
