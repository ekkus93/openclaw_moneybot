from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from skills.ledger_skill.service import LedgerService


def test_create_opportunity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "ledger.db")
        ledger = LedgerService(db_path)

        rec = ledger.create_opportunity(
            id="opp-1",
            name="Test bounty",
            category="bounty",
            source_url="https://example.com",
            status="new",
            created_at="2026-01-01T00:00:00Z",
        )
        assert rec["id"] == "opp-1"


def test_record_policy_decision() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "ledger.db")
        ledger = LedgerService(db_path)

        rec = ledger.record_policy_decision(
            id="pd-1",
            opportunity_id="opp-1",
            decision="allow",
            risk_level="low",
            matched_rules=["ALLOW_INTERNAL"],
            request_hash="hash-1",
            policy_version="v1",
            created_at="2026-01-01T00:00:00Z",
        )
        assert rec["decision"] == "allow"


def test_record_spend_request() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "ledger.db")
        ledger = LedgerService(db_path)

        rec = ledger.record_spend_request(
            id="sr-1",
            budget_plan_id="bp-1",
            policy_decision_id="pd-1",
            amount_usd=5.0,
            asset="BTC",
            recipient="recipient-addr",
            purpose="invoice",
            status="pending",
            created_at="2026-01-01T00:00:00Z",
        )
        assert rec["status"] == "pending"


def test_get_daily_spend_total() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "ledger.db")
        ledger = LedgerService(db_path)

        total = ledger.get_daily_spend_total("2026-01-01")
        assert total == 0.0


def test_export_tax_records_empty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "ledger.db")
        ledger = LedgerService(db_path)

        csv = ledger.export_tax_records()
        assert "txid" in csv


def test_foreign_keys_enforced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "ledger.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("CREATE TABLE t (id INTEGER PRIMARY KEY);")
        conn.commit()
        conn.close()
