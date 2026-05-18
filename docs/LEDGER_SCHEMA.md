# Ledger schema

Core tables:

- `opportunities`
- `policy_decisions`
- `tos_legal_checks`
- `budget_plans`
- `spend_requests`
- `btc_transactions`
- `evidence_records`
- `email_records`
- `experiment_reviews`
- `ledger_events`

Notable wallet-related fields:

- `spend_requests.status` tracks `proposed`, `approved`, `rejected`, `sending`, `sent`, `confirmed`, `failed`, and `cancelled`.
- `btc_transactions` stores `amount_usd_estimate`, `fee_usd_estimate`, and `total_usd_estimate`.
- `ledger_events` forms the append-only audit/event chain.

SQLite foreign keys are enabled on every connection.
