# Skill: ledger_skill

## Purpose

`ledger_skill` records all opportunities, decisions, actions, spend requests, payments, receipts, emails, evidence, and experiment outcomes for the OpenClaw MoneyBot.

This skill is mandatory. The bot must not spend funds, send business communications, submit public claims, or execute material actions without a ledger record.

## Design Goals

- Preserve a complete audit trail.
- Support tax/accounting review.
- Prevent the bot from lying to itself about results.
- Track budget limits and daily spend caps.
- Link actions to evidence and receipts.
- Make experiment review objective.

Use SQLite as the preferred local store. JSONL export is useful, but SQLite should be the source of truth.

## Database Location

Recommended path:

```text
/opt/openclawbot/data/moneybot.sqlite3
```

Permissions:

```text
owner: openclawbot or ledger service user
group: openclawbot
mode: 0600 or 0660 depending on service design
```

Wallet private keys, wallet passphrases, seed phrases, and wallet backups must never be stored in the ledger.

## Required Tables

### `opportunities`

```sql
CREATE TABLE IF NOT EXISTS opportunities (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  source_url TEXT,
  rules_url TEXT,
  status TEXT NOT NULL,
  required_spend_usd REAL,
  estimated_revenue_low_usd REAL,
  estimated_revenue_high_usd REAL,
  estimated_time_hours REAL,
  legal_risk TEXT,
  tos_risk TEXT,
  confidence TEXT,
  summary TEXT,
  raw_json TEXT NOT NULL
);
```

### `policy_checks`

```sql
CREATE TABLE IF NOT EXISTS policy_checks (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  opportunity_id TEXT,
  action_id TEXT,
  decision TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  confidence TEXT NOT NULL,
  blocked_reasons_json TEXT NOT NULL,
  required_mitigations_json TEXT NOT NULL,
  raw_json TEXT NOT NULL
);
```

### `tos_checks`

```sql
CREATE TABLE IF NOT EXISTS tos_checks (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  opportunity_id TEXT,
  decision TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  confidence TEXT NOT NULL,
  terms_available INTEGER NOT NULL,
  allowed_by_terms TEXT NOT NULL,
  red_flags_json TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  raw_json TEXT NOT NULL
);
```

### `experiments`

```sql
CREATE TABLE IF NOT EXISTS experiments (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  opportunity_id TEXT,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  approved_budget_usd REAL NOT NULL,
  max_loss_usd REAL NOT NULL,
  expected_revenue_low_usd REAL,
  expected_revenue_high_usd REAL,
  success_metrics_json TEXT NOT NULL,
  stop_conditions_json TEXT NOT NULL,
  plan_json TEXT NOT NULL
);
```

### `actions`

```sql
CREATE TABLE IF NOT EXISTS actions (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  experiment_id TEXT,
  opportunity_id TEXT,
  action_type TEXT NOT NULL,
  status TEXT NOT NULL,
  description TEXT NOT NULL,
  counterparty TEXT,
  platform TEXT,
  source_url TEXT,
  policy_check_id TEXT,
  tos_check_id TEXT,
  result_summary TEXT,
  raw_json TEXT NOT NULL
);
```

### `spend_requests`

```sql
CREATE TABLE IF NOT EXISTS spend_requests (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  experiment_id TEXT,
  action_id TEXT,
  status TEXT NOT NULL,
  amount_usd_estimate REAL NOT NULL,
  asset TEXT NOT NULL,
  destination TEXT,
  counterparty TEXT NOT NULL,
  purpose TEXT NOT NULL,
  category TEXT NOT NULL,
  max_loss_usd REAL NOT NULL,
  policy_check_id TEXT NOT NULL,
  budget_plan_id TEXT NOT NULL,
  wallet_quote_json TEXT,
  raw_json TEXT NOT NULL
);
```

### `wallet_transactions`

```sql
CREATE TABLE IF NOT EXISTS wallet_transactions (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  spend_request_id TEXT NOT NULL,
  chain TEXT NOT NULL,
  asset TEXT NOT NULL,
  amount_asset TEXT NOT NULL,
  amount_usd_estimate REAL NOT NULL,
  fee_asset TEXT,
  fee_usd_estimate REAL,
  destination TEXT NOT NULL,
  txid_or_signature TEXT NOT NULL,
  confirmation_status TEXT NOT NULL,
  purpose TEXT NOT NULL,
  raw_json TEXT NOT NULL
);
```

### `receipts`

```sql
CREATE TABLE IF NOT EXISTS receipts (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  experiment_id TEXT,
  action_id TEXT,
  spend_request_id TEXT,
  wallet_transaction_id TEXT,
  receipt_type TEXT NOT NULL,
  source_url TEXT,
  local_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  summary TEXT,
  raw_json TEXT NOT NULL
);
```

### `emails`

```sql
CREATE TABLE IF NOT EXISTS emails (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  action_id TEXT,
  experiment_id TEXT,
  direction TEXT NOT NULL,
  status TEXT NOT NULL,
  to_address TEXT,
  from_address TEXT,
  subject TEXT,
  message_id TEXT,
  thread_id TEXT,
  body_sha256 TEXT,
  local_body_path TEXT,
  policy_check_id TEXT,
  raw_json TEXT NOT NULL
);
```

### `tax_events`

```sql
CREATE TABLE IF NOT EXISTS tax_events (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  related_transaction_id TEXT,
  asset TEXT,
  amount_asset TEXT,
  fair_market_value_usd REAL,
  fee_usd REAL,
  cost_basis_usd REAL,
  gain_loss_usd REAL,
  note TEXT,
  raw_json TEXT NOT NULL
);
```

### `daily_limits`

```sql
CREATE TABLE IF NOT EXISTS daily_limits (
  day TEXT PRIMARY KEY,
  spend_usd REAL NOT NULL DEFAULT 0,
  email_count INTEGER NOT NULL DEFAULT 0,
  browser_submit_count INTEGER NOT NULL DEFAULT 0,
  wallet_tx_count INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
```

## Required Operations

The skill should support these operations through a narrow API or direct module calls:

```text
record_opportunity
record_tos_check
record_policy_check
create_experiment
record_action
create_spend_request
record_wallet_transaction
record_receipt
record_email
record_tax_event
get_daily_limits
increment_daily_limit
get_experiment_summary
export_jsonl
```

## Input/Output Contracts

### `create_spend_request`

Input:

```json
{
  "experiment_id": "string",
  "action_id": "string",
  "amount_usd_estimate": 8.0,
  "asset": "BTC",
  "destination": "string",
  "counterparty": "string",
  "purpose": "string",
  "category": "domain | hosting | listing_fee | software_credit | other",
  "max_loss_usd": 8.0,
  "policy_check_id": "string",
  "budget_plan_id": "string",
  "wallet_quote_json": {}
}
```

Output:

```json
{
  "spend_request_id": "string",
  "status": "created",
  "ledger_write_confirmed": true
}
```

## Required Invariants

- No wallet transaction may be recorded without a `spend_request_id`.
- No spend request may be created without `policy_check_id` and `budget_plan_id`.
- No email send may be recorded without an action and policy check.
- No receipt path may be recorded without SHA-256 hash.
- Daily spend totals must be updated atomically with wallet transaction recording.
- The ledger must append raw JSON for all skill outputs used in decision-making.
- The ledger must never store private keys, seed phrases, wallet passphrases, browser cookies, or login passwords.

## Budget Enforcement Support

Before any payment, wallet-governor should query:

```json
{
  "operation": "get_daily_limits",
  "day": "YYYY-MM-DD"
}
```

The wallet-governor must reject payment if daily limits would be exceeded.

## Tax/Event Notes

Record tax events for:

- Digital asset income received.
- Digital asset spending/payment.
- Digital asset conversion/swap, if ever allowed.
- Fees associated with wallet transactions.

The skill should not calculate final tax liability. It should preserve records sufficient for later review.

## Failure Behavior

If the ledger write fails, execution must stop. Do not proceed with email, payment, public posting, or purchase.

Return:

```json
{
  "status": "error",
  "execution_allowed": false,
  "error": "ledger write failed"
}
```

## Test Cases

### Test 1: Spend Without Policy Check

Input: `create_spend_request` missing `policy_check_id`.

Expected: reject write or mark invalid; execution not allowed.

### Test 2: Wallet Transaction Without Spend Request

Input: `record_wallet_transaction` without `spend_request_id`.

Expected: error.

### Test 3: Receipt Hash Required

Input: receipt path without SHA-256.

Expected: error.

### Test 4: Daily Limit Update

Input: two transactions same day totaling more than cap.

Expected: first allowed if under cap; second blocked by wallet-governor using ledger daily totals.

### Test 5: JSONL Export

Input: export all records for date range.

Expected: deterministic JSONL files with no secrets.
