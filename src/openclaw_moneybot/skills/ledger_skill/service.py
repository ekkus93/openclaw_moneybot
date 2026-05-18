"""Service wrapper for the ledger skill."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import (
    BudgetPlan,
    EmailDraftRecord,
    EvidenceRecord,
    ExperimentReview,
    LedgerRecord,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    TosLegalCheck,
    WalletTransactionRecord,
)
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.models import (
    LedgerEventEntry,
    LedgerTimelineEntry,
    LedgerWriteResult,
    SpendAuthorizationBundle,
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

    def record_ledger_record(
        self, record: LedgerRecord, *, idempotency_key: str | None = None
    ) -> LedgerWriteResult:
        return self.repository.record_ledger_record(record, idempotency_key=idempotency_key)

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

    def get_remaining_daily_limit(self, day: str, limit_usd: float) -> float:
        return self.repository.get_remaining_daily_limit(day, limit_usd)

    def get_remaining_weekly_limit(self, day: str, limit_usd: float) -> float:
        return self.repository.get_remaining_weekly_limit(day, limit_usd)

    def get_opportunity_timeline(self, opportunity_id: str) -> list[LedgerTimelineEntry]:
        return self.repository.get_opportunity_timeline(opportunity_id)

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        return self.repository.get_opportunity(opportunity_id)

    def get_policy_decision(self, policy_decision_id: str) -> PolicyDecision | None:
        return self.repository.get_policy_decision(policy_decision_id)

    def get_tos_legal_check(self, tos_legal_check_id: str) -> TosLegalCheck | None:
        return self.repository.get_tos_legal_check(tos_legal_check_id)

    def get_budget_plan(self, budget_plan_id: str) -> BudgetPlan | None:
        return self.repository.get_budget_plan(budget_plan_id)

    def get_spend_request(self, spend_request_id: str) -> SpendRequest | None:
        return self.repository.get_spend_request(spend_request_id)

    def update_spend_request_status(
        self,
        spend_request_id: str,
        status: str,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        return self.repository.update_spend_request_status(
            spend_request_id,
            status,
            idempotency_key=idempotency_key,
        )

    def list_spend_requests_for_opportunity(self, opportunity_id: str) -> list[SpendRequest]:
        return self.repository.list_spend_requests_for_opportunity(opportunity_id)

    def get_wallet_transaction(self, wallet_transaction_id: str) -> WalletTransactionRecord | None:
        return self.repository.get_wallet_transaction(wallet_transaction_id)

    def list_wallet_transactions_for_opportunity(
        self, opportunity_id: str
    ) -> list[WalletTransactionRecord]:
        return self.repository.list_wallet_transactions_for_opportunity(opportunity_id)

    def list_wallet_transactions_for_spend_request(
        self, spend_request_id: str
    ) -> list[WalletTransactionRecord]:
        return self.repository.list_wallet_transactions_for_spend_request(spend_request_id)

    def update_wallet_transaction_status(
        self,
        wallet_transaction_id: str,
        status: str,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        return self.repository.update_wallet_transaction_status(
            wallet_transaction_id,
            status,
            idempotency_key=idempotency_key,
        )

    def get_email_record(self, email_draft_id: str) -> EmailDraftRecord | None:
        return self.repository.get_email_record(email_draft_id)

    def list_email_records_for_opportunity(self, opportunity_id: str) -> list[EmailDraftRecord]:
        return self.repository.list_email_records_for_opportunity(opportunity_id)

    def get_evidence_record(self, evidence_id: str) -> EvidenceRecord | None:
        return self.repository.get_evidence_record(evidence_id)

    def list_evidence_for_related(
        self,
        *,
        related_type: RecordType,
        related_id: str,
    ) -> list[EvidenceRecord]:
        return self.repository.list_evidence_for_related(
            related_type=related_type,
            related_id=related_id,
        )

    def get_experiment_review(self, experiment_review_id: str) -> ExperimentReview | None:
        return self.repository.get_experiment_review(experiment_review_id)

    def ledger_event_exists(self, ledger_event_id: str) -> bool:
        return self.repository.ledger_event_exists(ledger_event_id)

    def get_spend_authorization_bundle(
        self, spend_request_id: str
    ) -> SpendAuthorizationBundle | None:
        return self.repository.get_spend_authorization_bundle(spend_request_id)

    def get_related_events(
        self,
        *,
        related_type: RecordType | None = None,
        related_id: str | None = None,
        event_type: str | None = None,
    ) -> list[LedgerEventEntry]:
        return self.repository.get_related_events(
            related_type=related_type,
            related_id=related_id,
            event_type=event_type,
        )

    def export_tax_records(self, output_path: Path) -> TaxExportResult:
        return self.repository.export_tax_records(output_path)

    def verify_event_chain(self) -> bool:
        return self.repository.verify_event_chain()
