"""Narrow in-process ledger API."""

from __future__ import annotations

from openclaw_moneybot.plugins.ledger_api.models import (
    LedgerApiAuditEventRequest,
    LedgerOpportunityBundle,
)
from openclaw_moneybot.shared import LedgerRecord
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.models import LedgerEventEntry, LedgerWriteResult
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class LedgerApi:
    """Typed, local-only ledger API surface."""

    def __init__(self, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service

    def get_opportunity_bundle(self, opportunity_id: str) -> LedgerOpportunityBundle:
        """Load an opportunity and its typed related records."""
        opportunity = self.ledger_service.get_opportunity(opportunity_id)
        if opportunity is None:
            msg = f"Unknown opportunity: {opportunity_id}"
            raise ValueError(msg)
        timeline = self.ledger_service.get_opportunity_timeline(opportunity_id)
        policy_decisions = []
        tos_legal_checks = []
        budget_plans = []
        for item in timeline:
            if item.related_type is RecordType.POLICY_DECISION:
                policy_record = self.ledger_service.get_policy_decision(item.related_id)
                if policy_record is not None:
                    policy_decisions.append(policy_record)
            elif item.related_type is RecordType.TOS_LEGAL_CHECK:
                tos_record = self.ledger_service.get_tos_legal_check(item.related_id)
                if tos_record is not None:
                    tos_legal_checks.append(tos_record)
            elif item.related_type is RecordType.BUDGET_PLAN:
                budget_record = self.ledger_service.get_budget_plan(item.related_id)
                if budget_record is not None:
                    budget_plans.append(budget_record)
        return LedgerOpportunityBundle(
            opportunity=opportunity,
            timeline=timeline,
            policy_decisions=policy_decisions,
            tos_legal_checks=tos_legal_checks,
            budget_plans=budget_plans,
            spend_requests=self.ledger_service.list_spend_requests_for_opportunity(opportunity_id),
            wallet_transactions=self.ledger_service.list_wallet_transactions_for_opportunity(
                opportunity_id
            ),
            email_records=self.ledger_service.list_email_records_for_opportunity(opportunity_id),
        )

    def get_event_log(
        self,
        *,
        related_type: RecordType | None = None,
        related_id: str | None = None,
        event_type: str | None = None,
    ) -> list[LedgerEventEntry]:
        """Read typed ledger events with explicit filters only."""
        return self.ledger_service.get_related_events(
            related_type=related_type,
            related_id=related_id,
            event_type=event_type,
        )

    def record_audit_event(self, request: LedgerApiAuditEventRequest) -> LedgerWriteResult:
        """Record a typed audit event without exposing raw SQL."""
        record = LedgerRecord(
            created_at=utc_now(),
            record_id=make_id("audit"),
            record_type=RecordType.AUDIT_EVENT,
            related_record_id=request.related_id,
            payload={"event_name": request.event_name, **request.payload},
        )
        return self.ledger_service.record_ledger_record(
            record,
            idempotency_key=request.idempotency_key,
        )
