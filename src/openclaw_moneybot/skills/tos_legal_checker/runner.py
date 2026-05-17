"""Service entrypoint for the TOS/legal checker."""

from __future__ import annotations

from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.tos_legal_checker.analysis import analyze_tos_legal_request
from openclaw_moneybot.skills.tos_legal_checker.models import (
    TosLegalCheckRequest,
    TosLegalCheckResult,
)


class TosLegalChecker:
    """Offline-first TOS/legal review service."""

    def __init__(self, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service

    def evaluate(self, request: TosLegalCheckRequest) -> TosLegalCheckResult:
        """Evaluate the request and persist the result to the ledger."""
        result = analyze_tos_legal_request(request)
        self.ledger_service.record_tos_legal_check(
            result.ledger_record,
            idempotency_key=f"tos:{result.ledger_record.tos_legal_check_id}",
        )
        return result
