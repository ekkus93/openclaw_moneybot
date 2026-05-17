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

# TODO — `wallet_governor_client`

## Goal

Implement the OpenClaw-facing client skill that talks only to a separate wallet-governor service. This skill must never access Bitcoin Core RPC credentials, private keys, wallet passphrases, wallet backups, or raw `bitcoin-cli`.

## Implementation tasks

### 1. Skill scaffolding

- [ ] Create implementation module for `wallet_governor_client`.
  - [ ] `models.py` for Pydantic v2 request/response contracts.
  - [ ] `client.py` for HTTP client calls to the governor service.
  - [ ] `validation.py` for client-side preflight validation.
  - [ ] `runner.py` for OpenClaw entrypoint.
- [ ] Add tests under `tests/skills/test_wallet_governor_client.py`.
- [ ] Use local fake HTTP server or fixture responses in tests.

### 2. Configuration

- [ ] Load wallet-governor base URL from config.
- [ ] Default URL to localhost only.
- [ ] Reject non-local URLs unless explicitly configured.
- [ ] Load client timeouts.
- [ ] Load allowed asset list.
- [ ] Load read-only vs spend-enabled mode.
- [ ] Fail closed if config is missing.

### 3. Input contracts

- [ ] Define `WalletBalanceRequest`.
- [ ] Define `WalletSpendRequest`.
  - [ ] `spend_request_id`
  - [ ] `budget_plan_id`
  - [ ] `policy_decision_id`
  - [ ] `ledger_event_id`
  - [ ] `amount_usd`
  - [ ] `asset`
  - [ ] `destination`
  - [ ] `counterparty`
  - [ ] `purpose`
  - [ ] `category`
  - [ ] `evidence_archive_ids`
- [ ] Define `WalletQuoteRequest` if quoting BTC amount/network fee before spending.
- [ ] Reject missing budget/policy/ledger IDs before calling service.
- [ ] Reject spend categories known to be prohibited.

### 4. Output contracts

- [ ] Define `WalletBalanceResult`.
  - [ ] `asset`
  - [ ] `confirmed_balance`
  - [ ] `unconfirmed_balance`
  - [ ] `usd_estimate`
  - [ ] `daily_spend_remaining_usd`
  - [ ] `service_limits`
- [ ] Define `WalletSpendResult`.
  - [ ] `status`: `sent | rejected | pending | error`
  - [ ] `txid`
  - [ ] `amount_btc`
  - [ ] `amount_usd_estimate`
  - [ ] `fee_btc`
  - [ ] `rejection_reasons`
  - [ ] `wallet_governor_decision_id`
- [ ] Include raw service response archive pointer, not private data.

### 5. Client-side preflight checks

- [ ] Require policy decision ID.
- [ ] Require budget plan ID.
- [ ] Require ledger event ID.
- [ ] Require evidence archive ID for invoice/recipient when spending.
- [ ] Reject `send_all` or full-balance language.
- [ ] Reject missing destination.
- [ ] Reject invalid BTC address format if BTC is used.
- [ ] Reject amount <= 0.
- [ ] Reject amount above configured client max even though service will also enforce.
- [ ] Reject unsupported assets.

### 6. Wallet-governor API integration

- [ ] Implement `GET /health` call.
- [ ] Implement `GET /balance` call.
- [ ] Implement `POST /quote-spend` call if supported.
- [ ] Implement `POST /send-small-payment` call.
- [ ] Implement `GET /daily-limits` call.
- [ ] Add retries only for safe idempotent calls.
- [ ] Do not retry spend calls unless idempotency key support is proven.
- [ ] Add request timeout.
- [ ] Treat connection failure as `error` and do not continue.

### 7. Ledger integration

- [ ] Before spend, confirm ledger has spend request record.
- [ ] After spend, write tx result to ledger.
- [ ] If service rejects, write rejection to ledger.
- [ ] If service errors, write error event to ledger.
- [ ] Link txid to evidence archive and budget plan.

### 8. Security constraints

- [ ] Ensure code never shells out to `bitcoin-cli`.
- [ ] Ensure code never reads Bitcoin datadir.
- [ ] Ensure code never logs passphrases, RPC cookies, private keys, or destination private metadata.
- [ ] Ensure service URL cannot be changed by LLM at runtime.
- [ ] Ensure spend-enabled mode is explicit and defaults to disabled.

### 9. Tests

- [ ] Test read-only balance call.
- [ ] Test spend disabled mode blocks spend.
- [ ] Test missing policy ID blocks spend before HTTP call.
- [ ] Test missing budget plan blocks spend before HTTP call.
- [ ] Test over-limit amount blocks spend before HTTP call.
- [ ] Test service rejection is preserved and recorded.
- [ ] Test service timeout returns safe error.
- [ ] Test no retry on spend by default.
- [ ] Test valid spend request serialization.

### 10. Acceptance criteria

- [ ] The skill cannot access wallet secrets or Bitcoin RPC directly.
- [ ] Every spend call requires policy, budget, ledger, and evidence references.
- [ ] The skill fails closed if wallet-governor service is unavailable.
- [ ] Service rejection reasons are preserved for review.
