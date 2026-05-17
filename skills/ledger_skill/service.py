from __future__ import annotations

import json
import sqlite3
from typing import Any

from skills.ledger_skill import hashing as ledger_hashing
from skills.ledger_skill.repository import (
    export_tax_records,
    get_daily_spend_total,
    get_opportunity_timeline,
    get_weekly_spend_total,
    migrate,
)


class LedgerService:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        migrate(db_path)

    def create_opportunity(
        self,
        id: str,
        name: str,
        category: str,
        source_url: str | None,
        status: str,
        created_at: str,
    ) -> dict[str, Any]:
        from skills.ledger_skill.repository import create_opportunity

        rec = create_opportunity(
            self.db_path,
            id,
            name,
            category,
            source_url,
            status,
            created_at,
        )
        self._log_event(
            "opportunity_created",
            "opportunity",
            id,
            rec,
        )
        return rec

    def record_policy_decision(
        self,
        id: str,
        opportunity_id: str,
        decision: str,
        risk_level: str,
        matched_rules: list[Any],
        request_hash: str,
        policy_version: str,
        created_at: str,
    ) -> dict[str, Any]:
        from skills.ledger_skill.repository import record_policy_decision

        rec = record_policy_decision(
            self.db_path,
            id=id,
            opportunity_id=opportunity_id,
            decision=decision,
            risk_level=risk_level,
            matched_rules=matched_rules,
            request_hash=request_hash,
            policy_version=policy_version,
            created_at=created_at,
        )
        self._log_event("policy_decision", "policy_decision", id, rec)
        return rec

    def record_tos_legal_check(
        self,
        id: str,
        opportunity_id: str,
        decision: str,
        confidence: str,
        red_flags: list[Any],
        evidence_ids: list[Any],
        created_at: str,
    ) -> dict[str, Any]:
        from skills.ledger_skill.repository import record_tos_legal_check

        rec = record_tos_legal_check(
            self.db_path,
            id=id,
            opportunity_id=opportunity_id,
            decision=decision,
            confidence=confidence,
            red_flags=red_flags,
            evidence_ids=evidence_ids,
            created_at=created_at,
        )
        self._log_event("tos_legal_check", "tos_legal_check", id, rec)
        return rec

    def record_budget_plan(
        self,
        id: str,
        opportunity_id: str,
        policy_decision_id: str,
        tos_legal_check_id: str,
        decision: str,
        recommended_budget_usd: float,
        max_loss_usd: float,
        expected_net_revenue_usd: float,
        success_metric: str,
        stop_condition: str,
        created_at: str,
    ) -> dict[str, Any]:
        from skills.ledger_skill.repository import record_budget_plan

        rec = record_budget_plan(
            self.db_path,
            id=id,
            opportunity_id=opportunity_id,
            policy_decision_id=policy_decision_id,
            tos_legal_check_id=tos_legal_check_id,
            decision=decision,
            recommended_budget_usd=recommended_budget_usd,
            max_loss_usd=max_loss_usd,
            expected_net_revenue_usd=expected_net_revenue_usd,
            success_metric=success_metric,
            stop_condition=stop_condition,
            created_at=created_at,
        )
        self._log_event("budget_plan", "budget_plan", id, rec)
        return rec

    def record_spend_request(
        self,
        id: str,
        budget_plan_id: str,
        policy_decision_id: str,
        amount_usd: float,
        asset: str,
        recipient: str,
        purpose: str,
        status: str,
        created_at: str,
    ) -> dict[str, Any]:
        from skills.ledger_skill.repository import record_spend_request

        rec = record_spend_request(
            self.db_path,
            id=id,
            budget_plan_id=budget_plan_id,
            policy_decision_id=policy_decision_id,
            amount_usd=amount_usd,
            asset=asset,
            recipient=recipient,
            purpose=purpose,
            status=status,
            created_at=created_at,
        )
        self._log_event("spend_request", "spend_request", id, rec)
        return rec

    def record_btc_transaction(
        self,
        id: str,
        spend_request_id: str,
        txid: str,
        amount_btc: float,
        fee_btc: float,
        usd_value_at_send: float,
        destination_address_hash_or_label: str,
        created_at: str,
    ) -> dict[str, Any]:
        from skills.ledger_skill.repository import record_btc_transaction

        rec = record_btc_transaction(
            self.db_path,
            id=id,
            spend_request_id=spend_request_id,
            txid=txid,
            amount_btc=amount_btc,
            fee_btc=fee_btc,
            usd_value_at_send=usd_value_at_send,
            destination_address_hash_or_label=destination_address_hash_or_label,
            created_at=created_at,
        )
        self._log_event("btc_transaction", "btc_transaction", id, rec)
        return rec

    def record_evidence(
        self,
        id: str,
        related_type: str,
        related_id: str,
        source_url: str | None,
        archive_path: str | None,
        content_sha256: str,
        created_at: str,
    ) -> dict[str, Any]:
        from skills.ledger_skill.repository import record_evidence

        rec = record_evidence(
            self.db_path,
            id=id,
            related_type=related_type,
            related_id=related_id,
            source_url=source_url,
            archive_path=archive_path,
            content_sha256=content_sha256,
            created_at=created_at,
        )
        self._log_event("evidence", "evidence_record", id, rec)
        return rec

    def record_email(
        self,
        id: str,
        opportunity_id: str,
        mode: str,
        recipient: str,
        subject: str,
        body_sha256: str,
        archive_path: str | None,
        created_at: str,
    ) -> dict[str, Any]:
        from skills.ledger_skill.repository import record_email

        rec = record_email(
            self.db_path,
            id=id,
            opportunity_id=opportunity_id,
            mode=mode,
            recipient=recipient,
            subject=subject,
            body_sha256=body_sha256,
            archive_path=archive_path,
            created_at=created_at,
        )
        self._log_event("email", "email_record", id, rec)
        return rec

    def record_experiment_review(
        self,
        id: str,
        opportunity_id: str,
        spent_usd: float,
        revenue_usd: float,
        net_usd: float,
        decision: str,
        lessons: list[Any],
        created_at: str,
    ) -> dict[str, Any]:
        from skills.ledger_skill.repository import record_experiment_review

        rec = record_experiment_review(
            self.db_path,
            id=id,
            opportunity_id=opportunity_id,
            spent_usd=spent_usd,
            revenue_usd=revenue_usd,
            net_usd=net_usd,
            decision=decision,
            lessons=lessons,
            created_at=created_at,
        )
        self._log_event("experiment_review", "experiment_review", id, rec)
        return rec

    def get_daily_spend_total(self, date: str) -> float:
        return get_daily_spend_total(self.db_path, date)

    def get_weekly_spend_total(self, week_start: str) -> float:
        return get_weekly_spend_total(self.db_path, week_start)

    def get_opportunity_timeline(
        self,
        opportunity_id: str,
    ) -> list[dict[str, Any]]:
        return get_opportunity_timeline(self.db_path, opportunity_id)

    def export_tax_records(self) -> str:
        return export_tax_records(self.db_path)

    def _log_event(
        self,
        event_type: str,
        related_type: str,
        related_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> None:
        conn = sqlite3.connect(self.db_path, isolation_level="DEFERRED")
        cursor = conn.cursor()

        payload_json = json.dumps(payload, default=str)

        cursor.execute(
            "SELECT event_hash FROM ledger_events "
            "ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        previous_event_hash = row[0] if row and row[0] else None

        event_hash = ledger_hashing.hash_event(
            previous_event_hash,
            payload_json,
        )

        insert_sql = (
            "INSERT INTO ledger_events "
            "(event_type, related_type, related_id, "
            "payload_json, previous_event_hash, "
            "event_hash, created_at, idempotency_key) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )

        try:
            cursor.execute(
                insert_sql,
                [
                    event_type,
                    related_type,
                    related_id,
                    payload_json,
                    previous_event_hash,
                    event_hash,
                    self._now(),
                    idempotency_key,
                ],
            )
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e) and idempotency_key:
                pass
            else:
                raise

        conn.commit()
        conn.close()

    @staticmethod
    def _now() -> str:
        from datetime import UTC, datetime

        return datetime.now(UTC).isoformat()
