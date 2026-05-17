from __future__ import annotations

import json
import sqlite3
from typing import Any


def apply_schema(cursor: sqlite3.Cursor) -> None:
    base_dir = __file__.replace("repository.py", "")
    schema_path = base_dir + "schema.sql"
    with open(schema_path) as f:
        sql = f.read()
    cursor.executescript(sql)


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path, isolation_level="DEFERRED")
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    apply_schema(cursor)
    cursor.execute(
        "INSERT OR IGNORE INTO schema_version "
        "(id, version) VALUES (1, 1)"
    )
    conn.commit()
    conn.close()


def _open(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path, isolation_level="DEFERRED")


def create_opportunity(
    db_path: str,
    id: str,
    name: str,
    category: str,
    source_url: str | None,
    status: str,
    created_at: str,
) -> dict[str, Any]:
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO opportunities "
        "(id, name, category, source_url, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [id, name, category, source_url, status, created_at],
    )
    conn.commit()
    conn.close()
    return {
        "id": id,
        "name": name,
        "category": category,
        "source_url": source_url,
        "status": status,
        "created_at": created_at,
    }


def record_policy_decision(
    db_path: str,
    id: str,
    opportunity_id: str,
    decision: str,
    risk_level: str,
    matched_rules: list[Any],
    request_hash: str,
    policy_version: str,
    created_at: str,
) -> dict[str, Any]:
    conn = _open(db_path)
    cursor = conn.cursor()
    matched_rules_json = json.dumps(matched_rules)
    cursor.execute(
        "INSERT INTO policy_decisions "
        "(id, opportunity_id, decision, risk_level, "
        "matched_rules_json, request_hash, policy_version, "
        "created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            id,
            opportunity_id,
            decision,
            risk_level,
            matched_rules_json,
            request_hash,
            policy_version,
            created_at,
        ],
    )
    conn.commit()
    conn.close()
    return {
        "id": id,
        "opportunity_id": opportunity_id,
        "decision": decision,
        "risk_level": risk_level,
        "matched_rules_json": matched_rules_json,
        "request_hash": request_hash,
        "policy_version": policy_version,
        "created_at": created_at,
    }


def record_tos_legal_check(
    db_path: str,
    id: str,
    opportunity_id: str,
    decision: str,
    confidence: str,
    red_flags: list[Any],
    evidence_ids: list[Any],
    created_at: str,
) -> dict[str, Any]:
    conn = _open(db_path)
    cursor = conn.cursor()
    red_flags_json = json.dumps(red_flags)
    evidence_ids_json = json.dumps(evidence_ids)
    cursor.execute(
        "INSERT INTO tos_legal_checks "
        "(id, opportunity_id, decision, confidence, "
        "red_flags_json, evidence_ids_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            id,
            opportunity_id,
            decision,
            confidence,
            red_flags_json,
            evidence_ids_json,
            created_at,
        ],
    )
    conn.commit()
    conn.close()
    return {
        "id": id,
        "opportunity_id": opportunity_id,
        "decision": decision,
        "confidence": confidence,
        "red_flags_json": red_flags_json,
        "evidence_ids_json": evidence_ids_json,
        "created_at": created_at,
    }


def record_budget_plan(
    db_path: str,
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
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO budget_plans "
        "(id, opportunity_id, policy_decision_id, "
        "tos_legal_check_id, decision, "
        "recommended_budget_usd, max_loss_usd, "
        "expected_net_revenue_usd, success_metric, "
        "stop_condition, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            id,
            opportunity_id,
            policy_decision_id,
            tos_legal_check_id,
            decision,
            recommended_budget_usd,
            max_loss_usd,
            expected_net_revenue_usd,
            success_metric,
            stop_condition,
            created_at,
        ],
    )
    conn.commit()
    conn.close()
    return {
        "id": id,
        "opportunity_id": opportunity_id,
        "policy_decision_id": policy_decision_id,
        "tos_legal_check_id": tos_legal_check_id,
        "decision": decision,
        "recommended_budget_usd": recommended_budget_usd,
        "max_loss_usd": max_loss_usd,
        "expected_net_revenue_usd": expected_net_revenue_usd,
        "success_metric": success_metric,
        "stop_condition": stop_condition,
        "created_at": created_at,
    }


def record_spend_request(
    db_path: str,
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
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO spend_requests "
        "(id, budget_plan_id, policy_decision_id, "
        "amount_usd, asset, recipient, purpose, "
        "status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            id,
            budget_plan_id,
            policy_decision_id,
            amount_usd,
            asset,
            recipient,
            purpose,
            status,
            created_at,
        ],
    )
    conn.commit()
    conn.close()
    return {
        "id": id,
        "budget_plan_id": budget_plan_id,
        "policy_decision_id": policy_decision_id,
        "amount_usd": amount_usd,
        "asset": asset,
        "recipient": recipient,
        "purpose": purpose,
        "status": status,
        "created_at": created_at,
    }


def record_btc_transaction(
    db_path: str,
    id: str,
    spend_request_id: str,
    txid: str,
    amount_btc: float,
    fee_btc: float,
    usd_value_at_send: float,
    destination_address_hash_or_label: str,
    created_at: str,
) -> dict[str, Any]:
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO btc_transactions "
        "(id, spend_request_id, txid, amount_btc, "
        "fee_btc, usd_value_at_send, "
        "destination_address_hash_or_label, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            id,
            spend_request_id,
            txid,
            amount_btc,
            fee_btc,
            usd_value_at_send,
            destination_address_hash_or_label,
            created_at,
        ],
    )
    conn.commit()
    conn.close()
    return {
        "id": id,
        "spend_request_id": spend_request_id,
        "txid": txid,
        "amount_btc": amount_btc,
        "fee_btc": fee_btc,
        "usd_value_at_send": usd_value_at_send,
        "destination_address_hash_or_label": destination_address_hash_or_label,
        "created_at": created_at,
    }


def record_evidence(
    db_path: str,
    id: str,
    related_type: str,
    related_id: str,
    source_url: str | None,
    archive_path: str | None,
    content_sha256: str,
    created_at: str,
) -> dict[str, Any]:
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO evidence_records "
        "(id, related_type, related_id, "
        "source_url, archive_path, content_sha256, "
        "created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            id,
            related_type,
            related_id,
            source_url,
            archive_path,
            content_sha256,
            created_at,
        ],
    )
    conn.commit()
    conn.close()
    return {
        "id": id,
        "related_type": related_type,
        "related_id": related_id,
        "source_url": source_url,
        "archive_path": archive_path,
        "content_sha256": content_sha256,
        "created_at": created_at,
    }


def record_email(
    db_path: str,
    id: str,
    opportunity_id: str,
    mode: str,
    recipient: str,
    subject: str,
    body_sha256: str,
    archive_path: str | None,
    created_at: str,
) -> dict[str, Any]:
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO email_records "
        "(id, opportunity_id, mode, recipient, "
        "subject, body_sha256, archive_path, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            id,
            opportunity_id,
            mode,
            recipient,
            subject,
            body_sha256,
            archive_path,
            created_at,
        ],
    )
    conn.commit()
    conn.close()
    return {
        "id": id,
        "opportunity_id": opportunity_id,
        "mode": mode,
        "recipient": recipient,
        "subject": subject,
        "body_sha256": body_sha256,
        "archive_path": archive_path,
        "created_at": created_at,
    }


def record_experiment_review(
    db_path: str,
    id: str,
    opportunity_id: str,
    spent_usd: float,
    revenue_usd: float,
    net_usd: float,
    decision: str,
    lessons: list[Any],
    created_at: str,
) -> dict[str, Any]:
    conn = _open(db_path)
    cursor = conn.cursor()
    lessons_json = json.dumps(lessons)
    cursor.execute(
        "INSERT INTO experiment_reviews "
        "(id, opportunity_id, spent_usd, revenue_usd, "
        "net_usd, decision, lessons_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            id,
            opportunity_id,
            spent_usd,
            revenue_usd,
            net_usd,
            decision,
            lessons_json,
            created_at,
        ],
    )
    conn.commit()
    conn.close()
    return {
        "id": id,
        "opportunity_id": opportunity_id,
        "spent_usd": spent_usd,
        "revenue_usd": revenue_usd,
        "net_usd": net_usd,
        "decision": decision,
        "lessons_json": lessons_json,
        "created_at": created_at,
    }


def get_daily_spend_total(db_path: str, date: str) -> float:
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(amount_usd), 0.0) "
        "FROM spend_requests "
        "WHERE created_at LIKE ? "
        "AND status != 'rejected'",
        [date + "%"],
    )
    total = cursor.fetchone()[0]
    conn.close()
    return float(total)


def get_weekly_spend_total(db_path: str, week_start: str) -> float:
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(amount_usd), 0.0) "
        "FROM spend_requests "
        "WHERE created_at >= ? "
        "AND status != 'rejected'",
        [week_start],
    )
    total = cursor.fetchone()[0]
    conn.close()
    return float(total)


def get_opportunity_timeline(
    db_path: str,
    opportunity_id: str,
) -> list[dict[str, Any]]:
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM ledger_events "
        "WHERE related_type = 'opportunity' "
        "AND related_id = ?",
        [opportunity_id],
    )
    rows = cursor.fetchall()
    conn.close()
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row, strict=True)) for row in rows
    ]


def export_tax_records(db_path: str) -> str:
    conn = _open(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT txid, amount_btc, fee_btc, "
        "usd_value_at_send, "
        "destination_address_hash_or_label, "
        "created_at "
        "FROM btc_transactions "
        "ORDER BY created_at"
    )
    rows = cursor.fetchall()
    conn.close()
    header = (
        "txid,amount_btc,fee_btc,"
        "usd_value_at_send,destination,created_at\n"
    )
    lines = [header]
    for row in rows:
        lines.append(",".join(str(v) for v in row))
    return "\n".join(lines)
