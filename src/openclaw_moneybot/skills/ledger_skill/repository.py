"""SQLite-backed ledger repository."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

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
from openclaw_moneybot.skills.ledger_skill.hashing import (
    canonical_json,
    compute_event_hash,
    verify_hash_chain,
)
from openclaw_moneybot.skills.ledger_skill.models import (
    LedgerEventEntry,
    LedgerTimelineEntry,
    LedgerWriteResult,
    TaxExportResult,
)
from openclaw_moneybot.utils.ids import make_id

SCHEMA_VERSION = 1


class LedgerRepository:
    """Repository for durable MoneyBot ledger operations."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        """Apply the initial schema if needed."""
        schema_path = Path(__file__).with_name("schema.sql")
        schema_sql = schema_path.read_text(encoding="utf-8")
        with self._connect() as connection:
            connection.executescript(schema_sql)
            connection.execute(
                """
                INSERT OR IGNORE INTO schema_version (version, applied_at)
                VALUES (?, datetime('now'))
                """,
                (SCHEMA_VERSION,),
            )

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, str | None]:
        return {key: row[key] for key in row.keys()}

    def _load_model(self, row: sqlite3.Row | None, model_type: type[Any]) -> Any | None:
        if row is None:
            return None
        return model_type.model_validate_json(str(row["raw_json"]))

    def _serialize_model(self, model: Any) -> str:
        return canonical_json(model.model_dump(mode="json"))

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        related_type: RecordType,
        related_id: str,
        payload_json: str,
        created_at: str,
        idempotency_key: str | None,
    ) -> LedgerWriteResult:
        existing_result = self._get_existing_event_result(connection, idempotency_key)
        if existing_result is not None:
            return existing_result

        previous = connection.execute(
            """
            SELECT event_hash
            FROM ledger_events
            ORDER BY created_at DESC, rowid DESC
            LIMIT 1
            """
        ).fetchone()
        previous_hash = None if previous is None else str(previous["event_hash"])
        event_hash = compute_event_hash(previous_hash, payload_json)
        event_id = make_id("ledger_event")
        connection.execute(
            """
            INSERT INTO ledger_events (
                id,
                event_type,
                related_type,
                related_id,
                payload_json,
                previous_event_hash,
                event_hash,
                created_at,
                idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                related_type.value,
                related_id,
                payload_json,
                previous_hash,
                event_hash,
                created_at,
                idempotency_key,
            ),
        )
        return LedgerWriteResult(record_id=related_id, ledger_event_id=event_id)

    def _get_existing_event_result(
        self, connection: sqlite3.Connection, idempotency_key: str | None
    ) -> LedgerWriteResult | None:
        """Return an existing event result for an idempotency key, if present."""
        if idempotency_key is not None:
            existing = connection.execute(
                """
                SELECT id, related_id
                FROM ledger_events
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                return LedgerWriteResult(
                    record_id=str(existing["related_id"]),
                    ledger_event_id=str(existing["id"]),
                    reused_existing_event=True,
                )
        return None

    def create_opportunity(
        self,
        opportunity: Opportunity,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(opportunity)
        with self._connect() as connection:
            existing_result = self._get_existing_event_result(connection, idempotency_key)
            if existing_result is not None:
                return existing_result
            connection.execute(
                """
                INSERT INTO opportunities (
                    id, created_at, updated_at, name, category, source_url, rules_url,
                    status, required_spend_usd, estimated_revenue_usd, max_loss_usd,
                    legal_risk, tos_risk, summary, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    opportunity.opportunity_id,
                    opportunity.created_at.isoformat(),
                    opportunity.created_at.isoformat(),
                    opportunity.name,
                    opportunity.category,
                    str(opportunity.source_url),
                    None if opportunity.rules_url is None else str(opportunity.rules_url),
                    opportunity.status,
                    opportunity.required_spend_usd,
                    opportunity.estimated_revenue_usd,
                    opportunity.max_loss_usd,
                    opportunity.legal_risk_precheck.value,
                    opportunity.tos_risk_precheck.value,
                    opportunity.summary,
                    payload_json,
                ),
            )
            return self._insert_event(
                connection,
                event_type="create_opportunity",
                related_type=RecordType.OPPORTUNITY,
                related_id=opportunity.opportunity_id,
                payload_json=payload_json,
                created_at=opportunity.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def record_ledger_record(
        self,
        record: LedgerRecord,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(record)
        with self._connect() as connection:
            return self._insert_event(
                connection,
                event_type=f"record_{record.record_type.value}",
                related_type=record.record_type,
                related_id=record.record_id,
                payload_json=payload_json,
                created_at=record.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def record_policy_decision(
        self,
        decision: PolicyDecision,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(decision)
        with self._connect() as connection:
            existing_result = self._get_existing_event_result(connection, idempotency_key)
            if existing_result is not None:
                return existing_result
            connection.execute(
                """
                INSERT INTO policy_decisions (
                    id, created_at, opportunity_id, decision, risk_level, confidence,
                    blocked_reasons_json, required_mitigations_json, matched_rules_json,
                    human_review_reason, safe_next_steps_json, policy_version,
                    request_hash, expires_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.policy_decision_id,
                    decision.created_at.isoformat(),
                    decision.opportunity_id,
                    decision.decision.value,
                    decision.risk_level.value,
                    decision.confidence.value,
                    canonical_json({"items": decision.blocked_reasons}),
                    canonical_json({"items": decision.required_mitigations}),
                    canonical_json({"items": decision.matched_rules}),
                    decision.human_review_reason,
                    canonical_json({"items": decision.safe_next_steps}),
                    decision.policy_version,
                    decision.request_fingerprint,
                    None if decision.expires_at is None else decision.expires_at.isoformat(),
                    payload_json,
                ),
            )
            return self._insert_event(
                connection,
                event_type="record_policy_decision",
                related_type=RecordType.POLICY_DECISION,
                related_id=decision.policy_decision_id,
                payload_json=payload_json,
                created_at=decision.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def record_tos_legal_check(
        self,
        check: TosLegalCheck,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(check)
        with self._connect() as connection:
            existing_result = self._get_existing_event_result(connection, idempotency_key)
            if existing_result is not None:
                return existing_result
            connection.execute(
                """
                INSERT INTO tos_legal_checks (
                    id, created_at, opportunity_id, decision, confidence,
                    platform_terms_summary, legal_risk_summary, tos_risk_summary,
                    red_flags_json, required_mitigations_json, required_records_json,
                    source_quotes_json, evidence_ids_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    check.tos_legal_check_id,
                    check.created_at.isoformat(),
                    check.opportunity_id,
                    check.decision.value,
                    check.confidence.value,
                    check.platform_terms_summary,
                    check.legal_risk_summary,
                    check.tos_risk_summary,
                    canonical_json({"items": check.red_flags}),
                    canonical_json({"items": check.required_mitigations}),
                    canonical_json({"items": check.required_records}),
                    canonical_json({"items": check.source_quotes_or_snippets}),
                    canonical_json({"items": check.evidence_archive_ids}),
                    payload_json,
                ),
            )
            return self._insert_event(
                connection,
                event_type="record_tos_legal_check",
                related_type=RecordType.TOS_LEGAL_CHECK,
                related_id=check.tos_legal_check_id,
                payload_json=payload_json,
                created_at=check.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def record_budget_plan(
        self,
        plan: BudgetPlan,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(plan)
        with self._connect() as connection:
            existing_result = self._get_existing_event_result(connection, idempotency_key)
            if existing_result is not None:
                return existing_result
            connection.execute(
                """
                INSERT INTO budget_plans (
                    id, created_at, opportunity_id, policy_decision_id, tos_legal_check_id,
                    decision, recommended_budget_usd, max_loss_usd, expected_gross_revenue_usd,
                    expected_net_revenue_usd, break_even_condition, success_metric, stop_condition,
                    required_records_json, risk_level, wallet_spend_request_allowed, reasons_json,
                    raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.budget_plan_id,
                    plan.created_at.isoformat(),
                    plan.opportunity_id,
                    plan.policy_decision_id,
                    plan.tos_legal_check_id,
                    plan.decision.value,
                    plan.recommended_budget_usd,
                    plan.max_loss_usd,
                    plan.expected_gross_revenue_usd,
                    plan.expected_net_revenue_usd,
                    plan.break_even_condition,
                    plan.success_metric,
                    plan.stop_condition,
                    canonical_json({"items": plan.required_records}),
                    plan.risk_level.value,
                    int(plan.wallet_spend_request_allowed),
                    canonical_json({"items": plan.reasons}),
                    payload_json,
                ),
            )
            return self._insert_event(
                connection,
                event_type="record_budget_plan",
                related_type=RecordType.BUDGET_PLAN,
                related_id=plan.budget_plan_id,
                payload_json=payload_json,
                created_at=plan.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def record_spend_request(
        self,
        spend_request: SpendRequest,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(spend_request)
        with self._connect() as connection:
            existing_result = self._get_existing_event_result(connection, idempotency_key)
            if existing_result is not None:
                return existing_result
            connection.execute(
                """
                INSERT INTO spend_requests (
                    id, created_at, opportunity_id, budget_plan_id, policy_decision_id,
                    ledger_record_id, amount_usd, asset, destination, counterparty, purpose,
                    category, evidence_archive_ids_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    spend_request.spend_request_id,
                    spend_request.created_at.isoformat(),
                    spend_request.opportunity_id,
                    spend_request.budget_plan_id,
                    spend_request.policy_decision_id,
                    spend_request.ledger_record_id,
                    spend_request.amount_usd,
                    spend_request.asset,
                    spend_request.destination,
                    spend_request.counterparty,
                    spend_request.purpose,
                    spend_request.category,
                    canonical_json({"items": spend_request.evidence_archive_ids}),
                    payload_json,
                ),
            )
            return self._insert_event(
                connection,
                event_type="record_spend_request",
                related_type=RecordType.SPEND_REQUEST,
                related_id=spend_request.spend_request_id,
                payload_json=payload_json,
                created_at=spend_request.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def record_btc_transaction(
        self,
        transaction: WalletTransactionRecord,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(transaction)
        with self._connect() as connection:
            existing_result = self._get_existing_event_result(connection, idempotency_key)
            if existing_result is not None:
                return existing_result
            connection.execute(
                """
                INSERT INTO btc_transactions (
                    id, created_at, spend_request_id, txid, amount_btc, fee_btc,
                    amount_usd_estimate, status, destination, purpose, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction.wallet_transaction_id,
                    transaction.created_at.isoformat(),
                    transaction.spend_request_id,
                    transaction.txid,
                    transaction.amount_btc,
                    transaction.fee_btc,
                    transaction.amount_usd_estimate,
                    transaction.status,
                    transaction.destination,
                    transaction.purpose,
                    payload_json,
                ),
            )
            return self._insert_event(
                connection,
                event_type="record_wallet_transaction",
                related_type=RecordType.WALLET_TRANSACTION,
                related_id=transaction.wallet_transaction_id,
                payload_json=payload_json,
                created_at=transaction.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def record_evidence(
        self,
        evidence: EvidenceRecord,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(evidence)
        with self._connect() as connection:
            existing_result = self._get_existing_event_result(connection, idempotency_key)
            if existing_result is not None:
                return existing_result
            connection.execute(
                """
                INSERT INTO evidence_records (
                    id, created_at, related_type, related_id, evidence_type, archive_path,
                    content_sha256, source_url, metadata_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.evidence_id,
                    evidence.created_at.isoformat(),
                    evidence.related_record_type.value,
                    evidence.related_record_id,
                    evidence.evidence_type,
                    evidence.archive_path,
                    evidence.content_sha256,
                    None if evidence.source_url is None else str(evidence.source_url),
                    canonical_json(evidence.metadata),
                    payload_json,
                ),
            )
            return self._insert_event(
                connection,
                event_type="record_evidence",
                related_type=RecordType.EVIDENCE,
                related_id=evidence.evidence_id,
                payload_json=payload_json,
                created_at=evidence.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def record_email(
        self,
        email: EmailDraftRecord,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(email)
        with self._connect() as connection:
            existing_result = self._get_existing_event_result(connection, idempotency_key)
            if existing_result is not None:
                return existing_result
            connection.execute(
                """
                INSERT INTO email_records (
                    id, created_at, opportunity_id, related_experiment_id, recipient,
                    subject, body, risk_flags_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email.email_draft_id,
                    email.created_at.isoformat(),
                    email.opportunity_id,
                    email.related_experiment_id,
                    email.to,
                    email.subject,
                    email.body,
                    canonical_json({"items": email.risk_flags}),
                    payload_json,
                ),
            )
            return self._insert_event(
                connection,
                event_type="record_email_draft",
                related_type=RecordType.EMAIL_DRAFT,
                related_id=email.email_draft_id,
                payload_json=payload_json,
                created_at=email.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def record_experiment_review(
        self,
        review: ExperimentReview,
        *,
        idempotency_key: str | None = None,
    ) -> LedgerWriteResult:
        payload_json = self._serialize_model(review)
        with self._connect() as connection:
            existing_result = self._get_existing_event_result(connection, idempotency_key)
            if existing_result is not None:
                return existing_result
            connection.execute(
                """
                INSERT INTO experiment_reviews (
                    id, created_at, opportunity_id, spent_usd, revenue_usd, net_usd,
                    roi_percent, outcome, decision, lessons_json, recommended_next_actions_json,
                    raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.experiment_review_id,
                    review.created_at.isoformat(),
                    review.opportunity_id,
                    review.spent_usd,
                    review.revenue_usd,
                    review.net_usd,
                    review.roi_percent,
                    review.outcome,
                    review.decision.value,
                    canonical_json({"items": review.lessons}),
                    canonical_json({"items": review.recommended_next_actions}),
                    payload_json,
                ),
            )
            return self._insert_event(
                connection,
                event_type="record_experiment_review",
                related_type=RecordType.EXPERIMENT_REVIEW,
                related_id=review.experiment_review_id,
                payload_json=payload_json,
                created_at=review.created_at.isoformat(),
                idempotency_key=idempotency_key,
            )

    def get_daily_spend_total(self, day: str) -> float:
        """Return total USD spend for a day."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(amount_usd_estimate), 0.0) AS total
                FROM btc_transactions
                WHERE substr(created_at, 1, 10) = ?
                """,
                (day,),
            ).fetchone()
        return float(row["total"]) if row is not None else 0.0

    def get_weekly_spend_total(self, day: str) -> float:
        """Return total USD spend for the 7-day window ending on the given day."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(amount_usd_estimate), 0.0) AS total
                FROM btc_transactions
                WHERE date(substr(created_at, 1, 10)) BETWEEN date(?) - 6 AND date(?)
                """,
                (day, day),
            ).fetchone()
        return float(row["total"]) if row is not None else 0.0

    def get_opportunity_timeline(self, opportunity_id: str) -> list[LedgerTimelineEntry]:
        """Collect ledger-linked records for a single opportunity."""
        query = """
            SELECT
                created_at,
                'opportunity' AS event_type,
                'opportunity' AS related_type,
                id AS related_id
            FROM opportunities WHERE id = ?
            UNION ALL
            SELECT created_at, 'policy_decision', 'policy_decision', id
            FROM policy_decisions WHERE opportunity_id = ?
            UNION ALL
            SELECT created_at, 'tos_legal_check', 'tos_legal_check', id
            FROM tos_legal_checks WHERE opportunity_id = ?
            UNION ALL
            SELECT created_at, 'budget_plan', 'budget_plan', id
            FROM budget_plans WHERE opportunity_id = ?
            UNION ALL
            SELECT created_at, 'spend_request', 'spend_request', id
            FROM spend_requests WHERE opportunity_id = ?
            UNION ALL
            SELECT created_at, 'email_draft', 'email_draft', id
            FROM email_records WHERE opportunity_id = ?
            UNION ALL
            SELECT created_at, 'experiment_review', 'experiment_review', id
            FROM experiment_reviews WHERE opportunity_id = ?
            ORDER BY created_at ASC
        """
        with self._connect() as connection:
            rows = connection.execute(
                query,
                (
                    opportunity_id,
                    opportunity_id,
                    opportunity_id,
                    opportunity_id,
                    opportunity_id,
                    opportunity_id,
                    opportunity_id,
                ),
            ).fetchall()
        return [
            LedgerTimelineEntry(
                created_at=str(row["created_at"]),
                event_type=str(row["event_type"]),
                related_type=RecordType(str(row["related_type"])),
                related_id=str(row["related_id"]),
            )
            for row in rows
        ]

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM opportunities WHERE id = ?",
                (opportunity_id,),
            ).fetchone()
        return self._load_model(row, Opportunity)

    def get_policy_decision(self, policy_decision_id: str) -> PolicyDecision | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM policy_decisions WHERE id = ?",
                (policy_decision_id,),
            ).fetchone()
        return self._load_model(row, PolicyDecision)

    def get_tos_legal_check(self, tos_legal_check_id: str) -> TosLegalCheck | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM tos_legal_checks WHERE id = ?",
                (tos_legal_check_id,),
            ).fetchone()
        return self._load_model(row, TosLegalCheck)

    def get_budget_plan(self, budget_plan_id: str) -> BudgetPlan | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM budget_plans WHERE id = ?",
                (budget_plan_id,),
            ).fetchone()
        return self._load_model(row, BudgetPlan)

    def get_spend_request(self, spend_request_id: str) -> SpendRequest | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM spend_requests WHERE id = ?",
                (spend_request_id,),
            ).fetchone()
        return self._load_model(row, SpendRequest)

    def list_spend_requests_for_opportunity(self, opportunity_id: str) -> list[SpendRequest]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT raw_json
                FROM spend_requests
                WHERE opportunity_id = ?
                ORDER BY created_at ASC
                """,
                (opportunity_id,),
            ).fetchall()
        return [
            SpendRequest.model_validate_json(str(row["raw_json"]))
            for row in rows
        ]

    def get_wallet_transaction(self, wallet_transaction_id: str) -> WalletTransactionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM btc_transactions WHERE id = ?",
                (wallet_transaction_id,),
            ).fetchone()
        return self._load_model(row, WalletTransactionRecord)

    def list_wallet_transactions_for_opportunity(
        self, opportunity_id: str
    ) -> list[WalletTransactionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT bt.raw_json
                FROM btc_transactions bt
                JOIN spend_requests sr ON sr.id = bt.spend_request_id
                WHERE sr.opportunity_id = ?
                ORDER BY bt.created_at ASC
                """,
                (opportunity_id,),
            ).fetchall()
        return [
            WalletTransactionRecord.model_validate_json(str(row["raw_json"]))
            for row in rows
        ]

    def get_email_record(self, email_draft_id: str) -> EmailDraftRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM email_records WHERE id = ?",
                (email_draft_id,),
            ).fetchone()
        return self._load_model(row, EmailDraftRecord)

    def list_email_records_for_opportunity(self, opportunity_id: str) -> list[EmailDraftRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT raw_json
                FROM email_records
                WHERE opportunity_id = ?
                ORDER BY created_at ASC
                """,
                (opportunity_id,),
            ).fetchall()
        return [
            EmailDraftRecord.model_validate_json(str(row["raw_json"]))
            for row in rows
        ]

    def get_evidence_record(self, evidence_id: str) -> EvidenceRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM evidence_records WHERE id = ?",
                (evidence_id,),
            ).fetchone()
        return self._load_model(row, EvidenceRecord)

    def list_evidence_for_related(
        self,
        *,
        related_type: RecordType,
        related_id: str,
    ) -> list[EvidenceRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT raw_json
                FROM evidence_records
                WHERE related_type = ? AND related_id = ?
                ORDER BY created_at ASC
                """,
                (related_type.value, related_id),
            ).fetchall()
        return [
            EvidenceRecord.model_validate_json(str(row["raw_json"]))
            for row in rows
        ]

    def get_experiment_review(self, experiment_review_id: str) -> ExperimentReview | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM experiment_reviews WHERE id = ?",
                (experiment_review_id,),
            ).fetchone()
        return self._load_model(row, ExperimentReview)

    def get_related_events(
        self,
        *,
        related_type: RecordType | None = None,
        related_id: str | None = None,
        event_type: str | None = None,
    ) -> list[LedgerEventEntry]:
        clauses: list[str] = []
        parameters: list[str] = []
        if related_type is not None:
            clauses.append("related_type = ?")
            parameters.append(related_type.value)
        if related_id is not None:
            clauses.append("related_id = ?")
            parameters.append(related_id)
        if event_type is not None:
            clauses.append("event_type = ?")
            parameters.append(event_type)
        where_clause = ""
        if clauses:
            where_clause = "WHERE " + " AND ".join(clauses)
        query = f"""
            SELECT id, created_at, event_type, related_type, related_id, payload_json
            FROM ledger_events
            {where_clause}
            ORDER BY created_at ASC, rowid ASC
        """
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            LedgerEventEntry(
                ledger_event_id=str(row["id"]),
                created_at=str(row["created_at"]),
                event_type=str(row["event_type"]),
                related_type=RecordType(str(row["related_type"])),
                related_id=str(row["related_id"]),
                payload=json.loads(str(row["payload_json"])),
            )
            for row in rows
        ]

    def export_tax_records(self, output_path: Path) -> TaxExportResult:
        """Export transaction tax/accounting rows as CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    bt.id AS wallet_transaction_id,
                    bt.created_at,
                    bt.txid,
                    bt.amount_btc,
                    bt.fee_btc,
                    bt.amount_usd_estimate,
                    sr.counterparty,
                    sr.purpose
                FROM btc_transactions bt
                JOIN spend_requests sr ON sr.id = bt.spend_request_id
                ORDER BY bt.created_at ASC
                """
            ).fetchall()

        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "wallet_transaction_id",
                    "created_at",
                    "txid",
                    "amount_btc",
                    "fee_btc",
                    "amount_usd_estimate",
                    "counterparty",
                    "purpose",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
        return TaxExportResult(output_path=output_path, row_count=len(rows))

    def verify_event_chain(self) -> bool:
        """Verify the ledger event chain integrity."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json, previous_event_hash, event_hash
                FROM ledger_events
                ORDER BY created_at ASC, rowid ASC
                """
            ).fetchall()
        return verify_hash_chain([self._row_to_dict(row) for row in rows])
