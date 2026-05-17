"""Models for the narrow ledger API."""

from __future__ import annotations

from pydantic import Field, JsonValue

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import (
    BudgetPlan,
    EmailDraftRecord,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    TosLegalCheck,
    WalletTransactionRecord,
)
from openclaw_moneybot.skills.ledger_skill.models import LedgerTimelineEntry


class LedgerOpportunityBundle(MoneyBotModel):
    """Typed ledger bundle for one opportunity."""

    opportunity: Opportunity
    timeline: list[LedgerTimelineEntry] = Field(default_factory=list)
    policy_decisions: list[PolicyDecision] = Field(default_factory=list)
    tos_legal_checks: list[TosLegalCheck] = Field(default_factory=list)
    budget_plans: list[BudgetPlan] = Field(default_factory=list)
    spend_requests: list[SpendRequest] = Field(default_factory=list)
    wallet_transactions: list[WalletTransactionRecord] = Field(default_factory=list)
    email_records: list[EmailDraftRecord] = Field(default_factory=list)


class LedgerApiAuditEventRequest(MoneyBotModel):
    """Explicit audit-event write request."""

    event_name: str
    related_id: str
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    idempotency_key: str
