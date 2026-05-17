CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY,
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    source_url TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS policy_decisions (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    matched_rules_json TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS tos_legal_checks (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    confidence TEXT NOT NULL,
    red_flags_json TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS budget_plans (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    policy_decision_id TEXT NOT NULL,
    tos_legal_check_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    recommended_budget_usd REAL NOT NULL,
    max_loss_usd REAL NOT NULL,
    expected_net_revenue_usd REAL NOT NULL,
    success_metric TEXT NOT NULL,
    stop_condition TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id),
    FOREIGN KEY (policy_decision_id) REFERENCES policy_decisions(id),
    FOREIGN KEY (tos_legal_check_id) REFERENCES tos_legal_checks(id)
);

CREATE TABLE IF NOT EXISTS spend_requests (
    id TEXT PRIMARY KEY,
    budget_plan_id TEXT NOT NULL,
    policy_decision_id TEXT NOT NULL,
    amount_usd REAL NOT NULL,
    asset TEXT NOT NULL,
    recipient TEXT NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (budget_plan_id) REFERENCES budget_plans(id),
    FOREIGN KEY (policy_decision_id) REFERENCES policy_decisions(id)
);

CREATE TABLE IF NOT EXISTS btc_transactions (
    id TEXT PRIMARY KEY,
    spend_request_id TEXT NOT NULL,
    txid TEXT NOT NULL,
    amount_btc REAL NOT NULL,
    fee_btc REAL NOT NULL,
    usd_value_at_send REAL NOT NULL,
    destination_address_hash_or_label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (spend_request_id) REFERENCES spend_requests(id)
);

CREATE TABLE IF NOT EXISTS evidence_records (
    id TEXT PRIMARY KEY,
    related_type TEXT NOT NULL,
    related_id TEXT NOT NULL,
    source_url TEXT,
    archive_path TEXT,
    content_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_records (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,
    archive_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS experiment_reviews (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    spent_usd REAL NOT NULL,
    revenue_usd REAL NOT NULL,
    net_usd REAL NOT NULL,
    decision TEXT NOT NULL,
    lessons_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS ledger_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    related_type TEXT NOT NULL,
    related_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_event_hash TEXT,
    event_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    idempotency_key TEXT UNIQUE
);
