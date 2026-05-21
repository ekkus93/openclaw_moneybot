"""Models for terms-change monitoring."""

from __future__ import annotations

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import RecordType, TermsChangeSeverity


class TermsChangeMonitorRequest(MoneyBotModel):
    """Request for comparing old and new rules snapshots."""

    opportunity_id: str
    prior_rules_text: str | None = None
    current_rules_text: str
    prior_evidence_archive_ids: list[str] = Field(default_factory=list)
    current_evidence_archive_ids: list[str] = Field(default_factory=list)
    prior_tos_legal_check_id: str | None = None
    prior_budget_plan_id: str | None = None


class TermsChangeMonitorResult(MoneyBotModel):
    """Structured result for rule and terms changes."""

    terms_change_id: str
    related_type: RecordType = RecordType.TERMS_CHANGE
    change_detected: bool
    severity: TermsChangeSeverity
    changed_fields: list[str] = Field(default_factory=list)
    summary: str
    requires_recheck: bool
    requires_budget_recheck: bool
    requires_policy_recheck: bool
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
