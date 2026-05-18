PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    source_url TEXT NOT NULL,
    rules_url TEXT,
    status TEXT NOT NULL,
    required_spend_usd REAL NOT NULL,
    estimated_revenue_usd REAL,
    max_loss_usd REAL NOT NULL,
    legal_risk TEXT NOT NULL,
    tos_risk TEXT NOT NULL,
    summary TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_decisions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    opportunity_id TEXT REFERENCES opportunities(id),
    decision TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    confidence TEXT NOT NULL,
    blocked_reasons_json TEXT NOT NULL,
    required_mitigations_json TEXT NOT NULL,
    matched_rules_json TEXT NOT NULL,
    human_review_reason TEXT,
    safe_next_steps_json TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    expires_at TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tos_legal_checks (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
    decision TEXT NOT NULL,
    confidence TEXT NOT NULL,
    platform_terms_summary TEXT NOT NULL,
    legal_risk_summary TEXT NOT NULL,
    tos_risk_summary TEXT NOT NULL,
    red_flags_json TEXT NOT NULL,
    required_mitigations_json TEXT NOT NULL,
    required_records_json TEXT NOT NULL,
    source_quotes_json TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS budget_plans (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
    policy_decision_id TEXT NOT NULL REFERENCES policy_decisions(id),
    tos_legal_check_id TEXT NOT NULL REFERENCES tos_legal_checks(id),
    decision TEXT NOT NULL,
    recommended_budget_usd REAL NOT NULL,
    max_loss_usd REAL NOT NULL,
    expected_gross_revenue_usd REAL NOT NULL,
    expected_net_revenue_usd REAL NOT NULL,
    break_even_condition TEXT NOT NULL,
    success_metric TEXT NOT NULL,
    stop_condition TEXT NOT NULL,
    required_records_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    wallet_spend_request_allowed INTEGER NOT NULL,
    reasons_json TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS spend_requests (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    opportunity_id TEXT REFERENCES opportunities(id),
    budget_plan_id TEXT NOT NULL REFERENCES budget_plans(id),
    policy_decision_id TEXT NOT NULL REFERENCES policy_decisions(id),
    ledger_record_id TEXT NOT NULL,
    amount_usd REAL NOT NULL,
    asset TEXT NOT NULL,
    destination TEXT NOT NULL,
    counterparty TEXT NOT NULL,
    purpose TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    evidence_archive_ids_json TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS btc_transactions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    spend_request_id TEXT NOT NULL REFERENCES spend_requests(id),
    txid TEXT NOT NULL UNIQUE,
    amount_btc TEXT NOT NULL,
    fee_btc TEXT NOT NULL,
    amount_usd_estimate REAL NOT NULL,
    fee_usd_estimate REAL NOT NULL DEFAULT 0,
    total_usd_estimate REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    destination TEXT NOT NULL,
    purpose TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_records (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    related_type TEXT NOT NULL,
    related_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    archive_path TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    source_url TEXT,
    metadata_json TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_records (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    opportunity_id TEXT REFERENCES opportunities(id),
    related_experiment_id TEXT,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    risk_flags_json TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_reviews (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
    spent_usd REAL NOT NULL,
    revenue_usd REAL NOT NULL,
    net_usd REAL NOT NULL,
    roi_percent REAL NOT NULL,
    outcome TEXT NOT NULL,
    decision TEXT NOT NULL,
    lessons_json TEXT NOT NULL,
    recommended_next_actions_json TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    related_type TEXT NOT NULL,
    related_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_event_hash TEXT,
    event_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    idempotency_key TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opportunities_created_at ON opportunities(created_at);
CREATE INDEX IF NOT EXISTS idx_policy_decisions_created_at ON policy_decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_tos_legal_checks_created_at ON tos_legal_checks(created_at);
CREATE INDEX IF NOT EXISTS idx_budget_plans_created_at ON budget_plans(created_at);
CREATE INDEX IF NOT EXISTS idx_spend_requests_created_at ON spend_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_spend_requests_budget_plan_id ON spend_requests(budget_plan_id);
CREATE INDEX IF NOT EXISTS idx_btc_transactions_created_at ON btc_transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_btc_transactions_spend_request_id ON btc_transactions(spend_request_id);
CREATE INDEX IF NOT EXISTS idx_evidence_records_related ON evidence_records(related_type, related_id);
CREATE INDEX IF NOT EXISTS idx_email_records_opportunity_id ON email_records(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_experiment_reviews_opportunity_id ON experiment_reviews(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_ledger_events_created_at ON ledger_events(created_at);
