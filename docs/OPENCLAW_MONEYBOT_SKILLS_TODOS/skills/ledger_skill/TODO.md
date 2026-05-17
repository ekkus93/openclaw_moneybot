# OpenClaw MoneyBot Skill Implementation TODOs

These TODO files are implementation handoff documents for building the OpenClaw MoneyBot skills from the existing `SKILL.md` specifications.

Assumptions:

- Python implementation is acceptable unless the repo dictates another language.
- Use Pydantic v2 for typed contracts and validation.
- Use SQLite for durable local state and tests.
- Prefer deterministic rule engines over LLM-only judgment for safety-critical decisions.
- Do not use external commercial LLM APIs. The bot will use the user's local LLM.
- Do not give OpenClaw direct access to private keys, wallet passphrases, raw Bitcoin RPC credentials, personal accounts, or unrestricted shell access.
- Every externally meaningful action must be written to the ledger before execution.

# TODO — `ledger_skill`

## Goal

Implement the durable, append-oriented accounting and audit trail for the MoneyBot. This skill records opportunities, decisions, plans, evidence, actions, spend requests, BTC transactions, email drafts, receipts, and experiment outcomes.

## Implementation tasks

### 1. Skill scaffolding

- [ ] Create implementation module for `ledger_skill`.
  - [ ] `models.py` for Pydantic v2 ledger contracts.
  - [ ] `schema.sql` or migration files for SQLite schema.
  - [ ] `repository.py` for database operations.
  - [ ] `service.py` for skill API.
  - [ ] `hashing.py` for tamper-evident record hashes.
- [ ] Add tests under `tests/skills/test_ledger_skill.py`.
- [ ] Use real temporary SQLite databases in tests.

### 2. Database schema

- [ ] Create `opportunities` table.
  - [ ] `id`
  - [ ] `name`
  - [ ] `category`
  - [ ] `source_url`
  - [ ] `status`
  - [ ] `created_at`
  - [ ] `updated_at`
- [ ] Create `policy_decisions` table.
  - [ ] `id`
  - [ ] `opportunity_id`
  - [ ] `decision`
  - [ ] `risk_level`
  - [ ] `matched_rules_json`
  - [ ] `request_hash`
  - [ ] `policy_version`
  - [ ] `created_at`
- [ ] Create `tos_legal_checks` table.
  - [ ] `id`
  - [ ] `opportunity_id`
  - [ ] `decision`
  - [ ] `confidence`
  - [ ] `red_flags_json`
  - [ ] `evidence_ids_json`
  - [ ] `created_at`
- [ ] Create `budget_plans` table.
  - [ ] `id`
  - [ ] `opportunity_id`
  - [ ] `policy_decision_id`
  - [ ] `tos_legal_check_id`
  - [ ] `decision`
  - [ ] `recommended_budget_usd`
  - [ ] `max_loss_usd`
  - [ ] `expected_net_revenue_usd`
  - [ ] `success_metric`
  - [ ] `stop_condition`
  - [ ] `created_at`
- [ ] Create `spend_requests` table.
  - [ ] `id`
  - [ ] `budget_plan_id`
  - [ ] `policy_decision_id`
  - [ ] `amount_usd`
  - [ ] `asset`
  - [ ] `recipient`
  - [ ] `purpose`
  - [ ] `status`
  - [ ] `created_at`
- [ ] Create `btc_transactions` table.
  - [ ] `id`
  - [ ] `spend_request_id`
  - [ ] `txid`
  - [ ] `amount_btc`
  - [ ] `fee_btc`
  - [ ] `usd_value_at_send`
  - [ ] `destination_address_hash_or_label`
  - [ ] `created_at`
- [ ] Create `evidence_records` table.
  - [ ] `id`
  - [ ] `related_type`
  - [ ] `related_id`
  - [ ] `source_url`
  - [ ] `archive_path`
  - [ ] `content_sha256`
  - [ ] `created_at`
- [ ] Create `email_records` table.
  - [ ] `id`
  - [ ] `opportunity_id`
  - [ ] `mode`: `draft | sent | received`
  - [ ] `recipient`
  - [ ] `subject`
  - [ ] `body_sha256`
  - [ ] `archive_path`
  - [ ] `created_at`
- [ ] Create `experiment_reviews` table.
  - [ ] `id`
  - [ ] `opportunity_id`
  - [ ] `spent_usd`
  - [ ] `revenue_usd`
  - [ ] `net_usd`
  - [ ] `decision`
  - [ ] `lessons_json`
  - [ ] `created_at`
- [ ] Create `ledger_events` append-only table.
  - [ ] `id`
  - [ ] `event_type`
  - [ ] `related_type`
  - [ ] `related_id`
  - [ ] `payload_json`
  - [ ] `previous_event_hash`
  - [ ] `event_hash`
  - [ ] `created_at`
  - [ ] `idempotency_key`

### 3. Migrations

- [ ] Add migration runner.
- [ ] Create initial schema migration.
- [ ] Add schema version table.
- [ ] Make migrations idempotent.
- [ ] Test migration from empty DB.
- [ ] Test migration does not destroy existing data.

### 4. Repository operations

- [ ] Implement `create_opportunity`.
- [ ] Implement `record_policy_decision`.
- [ ] Implement `record_tos_legal_check`.
- [ ] Implement `record_budget_plan`.
- [ ] Implement `record_spend_request`.
- [ ] Implement `record_btc_transaction`.
- [ ] Implement `record_evidence`.
- [ ] Implement `record_email`.
- [ ] Implement `record_experiment_review`.
- [ ] Implement `get_daily_spend_total`.
- [ ] Implement `get_weekly_spend_total`.
- [ ] Implement `get_opportunity_timeline`.
- [ ] Implement `export_tax_records`.

### 5. Tamper-evident event chain

- [ ] Serialize ledger events canonically.
- [ ] Hash each event payload.
- [ ] Link each event to previous event hash.
- [ ] Add verification function.
- [ ] Test tampering detection.
- [ ] Add repair/export guidance but do not silently repair tampered data.

### 6. Idempotency and consistency

- [ ] Require idempotency keys for externally meaningful events.
- [ ] Prevent duplicate spend records for same wallet-governor request.
- [ ] Prevent duplicate transaction records for same txid.
- [ ] Use SQLite transactions for multi-table writes.
- [ ] Enforce foreign keys.
- [ ] Add indexes for IDs, dates, txids, and opportunity status.

### 7. Tax/accounting fields

- [ ] Record digital asset, amount, txid, and USD value at transaction time.
- [ ] Record purpose and counterparty.
- [ ] Record cost basis field if available.
- [ ] Record fee amount separately.
- [ ] Record receipt/evidence pointer.
- [ ] Provide CSV export for tax/accounting review.
- [ ] Mark incomplete tax records as needing review.

### 8. Tests

- [ ] Test all table creation.
- [ ] Test every repository operation.
- [ ] Test foreign key constraints.
- [ ] Test duplicate txid rejection.
- [ ] Test idempotent repeated event.
- [ ] Test daily spend total.
- [ ] Test weekly spend total.
- [ ] Test tamper-evident hash chain verification.
- [ ] Test CSV export.
- [ ] Test missing required fields fail validation.

### 9. Acceptance criteria

- [ ] The ledger works offline with SQLite.
- [ ] Every MoneyBot action can be represented in the ledger.
- [ ] Spend cannot be recorded without policy and budget references.
- [ ] Evidence, email, and transaction records can be linked to opportunities.
- [ ] Ledger records are append-oriented and tamper-evident.
