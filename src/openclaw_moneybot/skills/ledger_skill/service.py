"""Service wrapper for the ledger skill."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import (
    BudgetPlan,
    EmailDraftRecord,
    EvidenceRecord,
    ExperimentReview,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    TosLegalCheck,
    WalletTransactionRecord,
)
from openclaw_moneybot.skills.ledger_skill.models import (
    LedgerTimelineEntry,
    LedgerWriteResult,
    TaxExportResult,
)
from openclaw_moneybot.skills.ledger_skill.repository import LedgerRepository


class LedgerService:
    """High-level API for ledger operations."""

    def __init__(self, repository: LedgerRepository) -> None:
        self.repository = repository

    @classmethod
    def from_db_path(cls, db_path: Path) -> LedgerService:
        """Create a service from a database path and run migrations."""
        repository = LedgerRepository(db_path)
        repository.migrate()
        return cls(repository)

    def create_opportunity(
        self, opportunity: Opportunity, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.create_opportunity(opportunity, idempotency_key=idempotency_key)

    def record_policy_decision(
        self, decision: PolicyDecision, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.record_policy_decision(decision, idempotency_key=idempotency_key)

    def record_tos_legal_check(
        self, check: TosLegalCheck, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.record_tos_legal_check(check, idempotency_key=idempotency_key)

    def record_budget_plan(
        self, plan: BudgetPlan, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.record_budget_plan(plan, idempotency_key=idempotency_key)

    def record_spend_request(
        self, spend_request: SpendRequest, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.record_spend_request(spend_request, idempotency_key=idempotency_key)

    def record_wallet_transaction(
        self, transaction: WalletTransactionRecord, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.record_btc_transaction(transaction, idempotency_key=idempotency_key)

    def record_evidence(
        self, evidence: EvidenceRecord, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.record_evidence(evidence, idempotency_key=idempotency_key)

    def record_email(
        self, email: EmailDraftRecord, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.record_email(email, idempotency_key=idempotency_key)

    def record_experiment_review(
        self, review: ExperimentReview, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.record_experiment_review(review, idempotency_key=idempotency_key)

    def get_daily_spend_total(self, day: str) -> float:
        return self.repository.get_daily_spend_total(day)

    def get_weekly_spend_total(self, day: str) -> float:
        return self.repository.get_weekly_spend_total(day)

    def get_opportunity_timeline(self, opportunity_id: str) -> list[LedgerTimelineEntry]:
        return self.repository.get_opportunity_timeline(opportunity_id)

    def export_tax_records(self, output_path: Path) -> TaxExportResult:
        return self.repository.export_tax_records(output_path)

    def verify_event_chain(self) -> bool:
        return self.repository.verify_event_chain()
