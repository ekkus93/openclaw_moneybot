# CODE_REVIEW1_TODO.md

# OpenClaw MoneyBot — Code Review 1 Comprehensive TODO

This TODO is based on `CODE_REVIEW1.md`.

## Important Assumption

Both implementation branches should start from **Copilot's current codebase**.

OpenCode's old implementation should be treated as discarded reference material only. Do **not** spend time repairing OpenCode's previous scaffold unless a task explicitly says to port an idea from it.

Primary direction:

```text
Reset OpenCode branch to Copilot branch head.
Use Copilot implementation as the shared base.
Fix safety-critical wallet, ledger, policy, evidence, and orchestration issues before enabling real BTC.
```

---

# Priority Legend

```text
P0 = must fix before any real wallet connection or real spend
P1 = must fix before serious dry-run/autonomous operation
P2 = important after core safety path is reliable
P3 = later enhancement
```

---

# 0. Global Rules for This Fix Pass

## 0.1 Branch/Repository Rules

- [ ] Use Copilot's current code as the base for both Copilot and OpenCode work.
- [ ] Reset OpenCode's branch to the head of Copilot's branch before implementation begins.
- [ ] Do not merge OpenCode's previous implementation into the Copilot base.
- [ ] Keep OpenCode's old code only as a historical reference if desired.
- [ ] Do not duplicate architecture between branches.
- [ ] Both agents should work from this TODO and the original project docs/specs.

## 0.2 Safety Rules

- [x] Do not connect to real Bitcoin Core during this fix pass.
- [x] Do not enable real wallet spending during this fix pass.
- [x] Keep `spend_enabled: false` by default.
- [x] Keep email in `draft_only` mode.
- [x] Do not add real email sending yet.
- [x] Do not add browser automation yet.
- [x] Do not add unrestricted shell execution.
- [x] Do not store wallet passphrases in the repo.
- [x] Do not store private keys in the repo.
- [x] Do not store Bitcoin Core RPC cookies in the repo.
- [x] Do not store seed phrases in the repo.
- [x] Do not put secrets in tests, fixtures, prompts, logs, or docs.
- [x] Do not add arbitrary Bitcoin RPC passthrough.
- [x] Do not add `sendall`, `dumpprivkey`, `dumpwallet`, or equivalent wallet operations.
- [x] Fail closed on missing, malformed, ambiguous, or unverified data.

## 0.3 Required Invariants

The fixed implementation must enforce:

- [x] Wallet spend cannot occur unless `spend_enabled == true`.
- [x] Wallet spend cannot occur unless policy decision is exactly `allow`.
- [x] Wallet spend cannot occur unless TOS/legal decision is exactly `proceed`.
- [x] Wallet spend cannot occur unless budget decision permits execution.
- [x] Wallet spend cannot occur unless budget explicitly allows wallet spend.
- [x] Wallet spend cannot occur unless spend amount is within approved budget.
- [x] Wallet spend cannot occur unless spend request exists in ledger before send.
- [x] Wallet spend cannot occur unless wallet-governor limits pass.
- [x] Wallet spend cannot occur for blocked categories.
- [x] Wallet spend cannot occur for unknown executable categories.
- [x] Wallet spend cannot occur for malformed or unsupported destinations.
- [x] Wallet spend cannot occur through `send-all`, `sweep`, `max`, or equivalent behavior.
- [x] Wallet-governor service must independently enforce all safety checks.
- [x] Wallet-governor service must not rely only on the client for authorization.
- [x] Every accepted, rejected, failed, or completed spend attempt must produce an audit/ledger record.
- [x] Evidence archive must not read arbitrary local files.
- [x] `human_review` must block autonomous execution.
- [x] Invalid LLM/plugin JSON must fail closed.

---

# 1. P0 — Harden Wallet-Governor Service Authorization

## 1.1 Problem

The wallet-governor client performs useful preflight checks, but the wallet-governor service does not independently verify policy, budget, TOS/legal, ledger, evidence, and category approvals before sending.

This is the most important safety issue.

The service must enforce the rules even if:

- OpenClaw is prompt-injected.
- The LLM emits bad tool calls.
- The client code has a bug.
- A local process calls the service directly.
- Someone reuses a stale ID.
- Someone sends syntactically valid but semantically unauthorized request JSON.

## 1.2 Target Areas

Likely paths:

```text
src/openclaw_moneybot/plugins/wallet_governor_service/
src/openclaw_moneybot/skills/wallet_governor_client/
src/openclaw_moneybot/skills/ledger_skill/
src/openclaw_moneybot/plugins/ledger_api/
tests/
```

## 1.3 Required Service-Side Checks

Inside `WalletGovernorService.capped_send()` or equivalent, add service-side checks.

### Spend Request Verification

- [x] Require `spend_request_id` in the send request.
- [x] Load the spend request from the ledger.
- [x] Reject if spend request does not exist.
- [x] Verify request amount matches ledger spend request amount.
- [x] Verify request destination matches ledger spend request destination.
- [x] Verify request category matches ledger spend request category.
- [x] Verify request counterparty matches ledger spend request counterparty, if present.
- [x] Verify request purpose matches or is consistent with ledger spend request purpose.
- [x] Verify spend request is in an eligible pre-send status.
- [x] Reject if spend request is already `sent`, `confirmed`, `failed`, `rejected`, or `cancelled`.
- [x] Reject if spend request is missing required foreign keys.
- [x] Reject if spend request was created without ledger/audit context.

### Policy Verification

- [x] Load `policy_decision_id` from ledger.
- [x] Reject if policy decision does not exist.
- [x] Require policy decision exactly `allow`.
- [x] Reject policy decision `block`.
- [x] Reject policy decision `needs_review`.
- [x] Verify policy decision relates to the same opportunity, experiment, budget plan, or spend request.
- [x] Verify policy decision is for an executable wallet/spend/purchase action, not unrelated research.
- [x] Reject stale policy decision if staleness is implemented.
- [x] Store rejection reason if verification fails.

### Budget Verification

- [x] Load `budget_plan_id` from ledger.
- [x] Reject if budget plan does not exist.
- [x] Require budget decision to be executable.
- [x] Reject budget decision `reject`.
- [x] Reject budget decision `simulate`.
- [x] Reject budget decision `needs_review`, if that enum exists.
- [x] Require budget plan explicitly allows wallet spend.
- [x] Require request amount <= approved/recommended wallet spend amount.
- [x] Require request amount <= maximum loss.
- [x] Verify the spend category is allowed by the budget plan.
- [x] Verify the budget plan has a success metric.
- [x] Verify the budget plan has a stop condition.
- [x] Verify the budget plan has a max-loss value.
- [x] Verify recurring-cost risk is resolved or absent.
- [x] Store rejection reason if verification fails.

### TOS/Legal Verification

- [x] Load the TOS/legal check associated with the opportunity or budget plan.
- [x] Reject if TOS/legal check does not exist.
- [x] Require TOS/legal decision exactly `proceed`.
- [x] Reject TOS/legal decision `human_review`.
- [x] Reject TOS/legal decision `reject`.
- [x] Reject missing or malformed TOS/legal result.
- [x] Verify TOS/legal check relates to the same opportunity.
- [x] Verify required evidence from TOS/legal check exists.
- [x] Store rejection reason if verification fails.

### Category Verification

- [x] Require spend category.
- [x] Reject unknown spend category by default.
- [x] Reject blocked categories:
  - [ ] gambling
  - [ ] prediction markets
  - [ ] securities trading
  - [ ] options trading
  - [ ] forex trading
  - [ ] futures trading
  - [ ] leveraged products
  - [ ] autonomous crypto trading
  - [ ] DeFi/yield farming
  - [ ] NFT trading/minting/speculation
  - [ ] token speculation
  - [ ] airdrop farming
  - [ ] money transmission
  - [ ] escrow
  - [ ] exchange/broker behavior
  - [ ] mixing/tumbling
  - [ ] KYC evasion
  - [ ] fake accounts
  - [ ] account farming
  - [ ] fake reviews
  - [ ] spam
  - [ ] phishing
  - [ ] malware
  - [ ] credential harvesting
  - [ ] scraping against terms
  - [ ] paywall bypass
  - [ ] handling other people's funds
  - [ ] impersonation
  - [ ] deceptive claims
- [x] Allow only explicitly permitted spend categories, such as:
  - [ ] infrastructure
  - [ ] domain
  - [ ] hosting
  - [ ] listing_fee
  - [ ] software_tool
  - [ ] bounty_submission_fee, only if terms are clear
  - [ ] experiment_material, only if budget-approved

### Evidence Verification

- [x] Require evidence artifact IDs for wallet spend if configured.
- [x] Verify each evidence artifact exists in ledger.
- [x] Verify evidence artifact path exists on disk, if applicable.
- [x] Verify evidence artifact has hash metadata.
- [x] Verify evidence artifact is linked to the relevant opportunity, experiment, budget plan, or spend request.
- [x] Reject if required evidence is missing.
- [x] Reject if evidence is unrelated to the spend.
- [x] Store rejection reason if verification fails.

### Destination Verification

- [x] Require destination address.
- [x] Validate destination address for configured asset/network.
- [x] Reject empty address.
- [x] Reject placeholder address.
- [x] Reject test placeholder strings.
- [x] Reject malformed Bitcoin address.
- [x] Reject unsupported network address.
- [x] Reject destination if configured blocklist contains it.
- [x] Reject requests containing `send_all`, `sweep`, `max`, `all funds`, or equivalent semantics.
- [x] Ensure no API path allows unconstrained destination mutation after validation.

### Amount and Limit Verification

- [x] Require positive amount.
- [x] Reject zero amount.
- [x] Reject negative amount.
- [x] Reject amount above max single payment.
- [x] Reject amount above daily remaining limit.
- [x] Reject amount above weekly remaining limit.
- [x] Reject amount above approved budget.
- [x] Reject amount above wallet available balance after estimated fee.
- [x] Include fees in limit calculation or explicitly document if not.
- [x] Recommended: apply daily/weekly limits to payment amount plus estimated fee.
- [x] Reject if amount cannot be converted to BTC or configured asset.
- [x] Store rejection reason if verification fails.

## 1.4 Ledger/Audit Requirements

For every `send-small-payment` attempt:

- [x] Write audit event when request is received.
- [x] Write audit event before validation begins.
- [x] Write audit event for each rejection path.
- [x] Write audit event before wallet backend send.
- [x] Write audit event after successful wallet backend send.
- [x] Write audit event after wallet backend failure.
- [x] Update spend request status on rejection.
- [x] Update spend request status on backend failure.
- [x] Update spend request status on success.
- [x] Record wallet transaction on success.
- [x] Preserve sanitized raw request JSON.
- [x] Preserve sanitized raw response JSON.
- [x] Never log wallet passphrase.
- [x] Never log RPC cookie.
- [x] Never log private key or seed material.

## 1.5 Required Rejection Reason Codes

Add structured reason codes such as:

```text
spend_disabled
spend_request_missing
spend_request_not_found
spend_request_status_invalid
spend_request_mismatch
policy_missing
policy_not_allow
budget_missing
budget_not_executable
budget_wallet_spend_not_allowed
budget_amount_exceeded
tos_missing
tos_not_proceed
category_missing
category_unknown
category_blocked
evidence_missing
evidence_unrelated
destination_missing
destination_invalid
send_all_blocked
amount_invalid
amount_exceeds_single_limit
amount_exceeds_daily_limit
amount_exceeds_weekly_limit
amount_exceeds_budget
insufficient_balance
fee_quote_failed
idempotency_conflict
backend_error
```

## 1.6 Required Tests

Add tests proving:

- [x] Service rejects when `spend_enabled == false`.
- [x] Service rejects missing spend request ID.
- [x] Service rejects unknown spend request ID.
- [x] Service rejects already-sent spend request.
- [x] Service rejects mismatched amount.
- [x] Service rejects mismatched destination.
- [x] Service rejects mismatched category.
- [x] Service rejects missing policy decision.
- [x] Service rejects policy `block`.
- [x] Service rejects policy `needs_review`.
- [x] Service allows only policy `allow`.
- [x] Service rejects missing budget plan.
- [x] Service rejects non-executable budget.
- [x] Service rejects budget that does not allow wallet spend.
- [x] Service rejects amount above approved budget.
- [x] Service rejects missing TOS/legal check.
- [x] Service rejects TOS/legal `human_review`.
- [x] Service rejects TOS/legal `reject`.
- [x] Service allows only TOS/legal `proceed`.
- [x] Service rejects blocked category.
- [x] Service rejects unknown category.
- [x] Service rejects missing evidence.
- [x] Service rejects unrelated evidence.
- [x] Service rejects malformed destination.
- [x] Service rejects placeholder destination.
- [x] Service rejects send-all-like request.
- [x] Service rejects amount above max single limit.
- [x] Service rejects amount above daily limit.
- [x] Service rejects amount above weekly limit.
- [x] Service rejects insufficient balance.
- [x] Service writes audit record on rejection.
- [x] Service writes audit record on success.
- [x] Service does not call wallet backend on validation failure.
- [x] Service calls wallet backend exactly once on valid send.
- [x] Idempotent retry returns same result for identical request.
- [x] Idempotent retry rejects conflicting request data.

---

# 2. P0 — Fix Wallet Client TOS `human_review` Bug

## 2.1 Problem

The wallet client currently permits TOS/legal `human_review` for wallet spend. This is wrong.

Autonomous spend must require exactly:

```text
TOS/legal decision == proceed
```

`human_review` means stop and wait for human review.

## 2.2 Target Area

Likely path:

```text
src/openclaw_moneybot/skills/wallet_governor_client/validation.py
```

## 2.3 Required Fix

- [x] Find wallet preflight validation for TOS/legal checks.
- [x] Remove `HUMAN_REVIEW` from allowed TOS decisions.
- [x] Require TOS decision exactly `PROCEED`.
- [x] Treat `HUMAN_REVIEW` as blocking.
- [x] Treat `REJECT` as blocking.
- [x] Treat missing TOS check as blocking.
- [x] Treat malformed TOS check as blocking.
- [x] Update error message to say autonomous wallet spend requires TOS/legal `proceed`.

## 2.4 Tests

- [x] Add test: wallet client rejects TOS `human_review`.
- [x] Add test: wallet client rejects TOS `reject`.
- [x] Add test: wallet client rejects missing TOS.
- [x] Add test: wallet client allows preflight only for TOS `proceed`.
- [x] Add regression test named clearly for this issue.

---

# 3. P0 — Fix Weekly Spend SQL

## 3.1 Problem

Weekly spend query appears to use invalid SQLite date arithmetic:

```sql
date(?) - 6
```

SQLite date modifiers should be used:

```sql
date(?, '-6 days')
```

This is safety-critical because weekly spending limits depend on it.

## 3.2 Target Area

Likely path:

```text
src/openclaw_moneybot/skills/ledger_skill/repository.py
```

## 3.3 Required Fix

- [x] Locate weekly spend total query.
- [x] Replace invalid date arithmetic with valid SQLite date modifier syntax.
- [x] Include today and previous six calendar days.
- [x] Exclude transactions older than six days before the reference date.
- [x] Ensure query uses canonical timestamp field.
- [x] Ensure only actual spend statuses count.
- [x] Do not count rejected spend.
- [x] Do not count cancelled spend.
- [x] Do not count validation-only quote requests.
- [x] Decide and document whether pending/sent unconfirmed spends count.
- [x] Recommended: count `sent` and `confirmed`; do not count `rejected`, `failed`, or `cancelled`.

## 3.4 Tests

- [x] Weekly total includes spend from today.
- [x] Weekly total includes spend from six days ago.
- [x] Weekly total excludes spend from seven days ago.
- [x] Weekly total excludes rejected spend.
- [x] Weekly total excludes failed spend.
- [x] Weekly total excludes cancelled spend.
- [x] Weekly total includes sent spend.
- [x] Weekly total includes confirmed spend.
- [x] Daily total behavior remains correct.
- [x] Weekly limit rejection triggers correctly.

---

# 4. P0 — Clarify Client/Service Ledger Responsibility

## 4.1 Problem

Client and service responsibilities for spend request creation are muddled. The client may prewrite a spend request, while the service may also create one.

This can cause duplicate, conflicting, or ambiguous ledger records.

## 4.2 Required Canonical Flow

Implement this exact flow:

```text
1. Client creates spend request in ledger.
2. Client calls wallet-governor service with spend_request_id.
3. Service loads existing spend request from ledger.
4. Service verifies policy, budget, TOS/legal, evidence, category, destination, amount, and limits.
5. Service sends through wallet backend only after all checks pass.
6. Service records wallet transaction.
7. Service updates existing spend request status.
```

## 4.3 Required Changes

- [x] Identify all code paths that create spend requests.
- [x] Remove service behavior that creates independent spend requests for authorization.
- [x] Make service require `spend_request_id`.
- [x] Make service verify the existing ledger spend request.
- [x] Make service reject if request data conflicts with ledger data.
- [x] Make wallet transaction link to existing spend request.
- [x] Make service update existing spend request status.
- [x] Make idempotency key attach to existing spend request.
- [x] Document canonical flow in `docs/WALLET_GOVERNOR_DESIGN.md`.

## 4.4 Required Spend Statuses

Define or confirm canonical statuses:

```text
proposed
approved
rejected
sending
sent
confirmed
failed
cancelled
```

Implement expected transitions:

- [x] `proposed -> approved`
- [x] `approved -> sending`
- [x] `sending -> sent`
- [x] `sent -> confirmed`
- [x] `proposed/approved -> rejected`
- [x] `sending -> failed`
- [x] `proposed/approved -> cancelled`

## 4.5 Tests

- [x] Service rejects send request without spend request ID.
- [x] Service rejects unknown spend request ID.
- [x] Service rejects mismatched amount.
- [x] Service rejects mismatched destination.
- [x] Service rejects mismatched category.
- [x] Service updates existing spend request to `sent` after success.
- [x] Service updates existing spend request to `rejected` after validation rejection.
- [x] Service updates existing spend request to `failed` after backend error.
- [x] No duplicate spend request is created during send.
- [x] Wallet transaction links to existing spend request.

---

# 5. P0 — Make Spend Rejections Durable and Auditable

## 5.1 Required Work

- [x] Add audit event for wallet send request received.
- [x] Add audit event for wallet quote request received, if quote audit is desired.
- [x] Add audit event for validation rejection.
- [x] Add audit event for spend disabled rejection.
- [x] Add audit event for limit rejection.
- [x] Add audit event for policy rejection.
- [x] Add audit event for TOS/legal rejection.
- [x] Add audit event for budget rejection.
- [x] Add audit event for evidence rejection.
- [x] Add audit event for destination rejection.
- [x] Add audit event for backend failure.
- [x] Add audit event for backend success.
- [x] Include reason code.
- [x] Include related record IDs.
- [x] Include sanitized request summary.
- [x] Exclude all secrets.

## 5.2 Tests

- [x] Rejected spend writes audit event.
- [x] Successful spend writes audit event.
- [x] Backend failure writes audit event.
- [x] Audit event includes reason code.
- [x] Audit event includes related IDs.
- [x] Audit event does not include passphrase.
- [x] Audit event does not include private key.
- [x] Audit event does not include RPC cookie.

---

# 6. P1 — Add Local Wallet-Governor HTTP Service

## 6.1 Problem

The client expects HTTP endpoints, but service currently appears to be in-process/test-oriented.

## 6.2 Required Endpoints

Implement local-only HTTP service, likely FastAPI:

```text
GET  /health
GET  /balance
GET  /limits
POST /quote-spend
POST /send-small-payment
```

## 6.3 Endpoint Requirements

### `GET /health`

- [x] Return status.
- [x] Return service version if available.
- [x] Return backend mode: `fake`, `bitcoin_core`, or equivalent.
- [x] Do not expose secrets.

### `GET /balance`

- [x] Return asset.
- [x] Return network.
- [x] Return confirmed/available balance if available.
- [x] Return spend enabled flag.
- [x] Do not expose wallet internals.

### `GET /limits`

- [x] Return max single payment.
- [x] Return daily limit.
- [x] Return weekly limit.
- [x] Return remaining daily limit.
- [x] Return remaining weekly limit.
- [x] Return allowed categories if safe.
- [x] Return blocked categories if safe.

### `POST /quote-spend`

- [x] Validate schema.
- [x] Validate destination.
- [x] Estimate amount and fee.
- [x] Return quote only.
- [x] Do not send.
- [x] Do not unlock wallet unless absolutely required.

### `POST /send-small-payment`

- [x] Validate schema.
- [x] Run all P0 service-side checks.
- [x] Enforce limits.
- [x] Send only after all gates pass.
- [x] Record ledger/audit state.
- [x] Return txid and metadata on success.
- [x] Return structured rejection on failure.

## 6.4 Security Requirements

- [x] Bind to `127.0.0.1` by default.
- [x] Reject non-local bind unless explicitly configured.
- [x] Add request body size limit.
- [x] Add timeout handling.
- [x] Do not expose tracebacks in normal API errors.
- [x] Do not log secrets.
- [x] Do not expose raw wallet RPC.

## 6.5 Tests

- [x] `/health` works.
- [x] `/balance` works.
- [x] `/limits` works.
- [x] `/quote-spend` happy path works with fake backend.
- [x] `/quote-spend` rejects invalid destination.
- [x] `/send-small-payment` rejects spend disabled.
- [x] `/send-small-payment` rejects missing policy.
- [x] `/send-small-payment` rejects TOS `human_review`.
- [x] `/send-small-payment` succeeds with fake backend and valid ledger approvals.
- [x] Server defaults to localhost bind.

---

# 7. P1 — Add Bitcoin Core Backend Skeleton

## 7.1 Scope

Add the backend implementation, but keep it disabled by default. Tests should use fake/stub RPC, not real Bitcoin Core.

## 7.2 Required Backend

Create:

```text
BitcoinCoreWalletBackend
```

Required methods:

- [x] `health_check()`
- [x] `get_balance()`
- [x] `estimate_fee()`
- [x] `quote_send()`
- [x] `send_to_address()`
- [x] `get_transaction()`
- [x] `wallet_unlock()`, if encrypted wallet
- [x] `wallet_lock()`, if encrypted wallet

## 7.3 RPC Safety

- [x] Read RPC settings from service-only config/env.
- [x] Do not expose RPC cookie to OpenClaw.
- [x] Do not expose wallet passphrase to OpenClaw.
- [x] Bind/use localhost RPC only.
- [x] Use named wallet only.
- [x] Do not support arbitrary RPC passthrough.
- [x] Do not implement `sendall`.
- [x] Do not implement `dumpprivkey`.
- [x] Do not implement `dumpwallet`.
- [x] Do not implement raw wallet passphrase endpoint.
- [x] Normalize RPC errors into typed backend errors.

## 7.4 Unlock/Lock Safety

- [x] Unlock only immediately before send.
- [x] Use short unlock timeout.
- [x] Lock wallet immediately after send.
- [x] Lock wallet in a `finally` block.
- [x] Lock wallet after failed send.
- [x] Never log passphrase.

## 7.5 Tests

- [x] Balance parsing with fake RPC.
- [x] Fee estimate parsing with fake RPC.
- [x] Successful send calls expected RPC sequence.
- [x] Wallet lock called after success.
- [x] Wallet lock called after failure.
- [x] RPC errors become typed errors.
- [x] Passphrase never appears in logs/responses.
- [x] Unsupported RPC passthrough impossible.
- [x] Malformed destination rejects before RPC call.
- [x] Over-limit amount rejects before RPC call.

---

# 8. P1 — Restrict Evidence File Reads

## 8.1 Problem

The evidence archiver can read arbitrary local paths through `content_bytes_path` unless it is constrained.

## 8.2 Required Fix

- [x] Define approved input/workspace root.
- [x] Resolve source path using `Path.resolve()`.
- [x] Resolve workspace root using `Path.resolve()`.
- [x] Verify source path is inside approved workspace root.
- [x] Reject absolute paths outside workspace.
- [x] Reject symlink escapes.
- [x] Reject directories.
- [x] Reject non-regular files.
- [x] Enforce maximum file size.
- [x] Reject null-byte paths.
- [x] Reject sensitive paths:
  - [ ] `/etc`
  - [ ] `/root`
  - [ ] `/home/*/.ssh`
  - [ ] browser profile cookie stores
  - [ ] Bitcoin Core datadir
  - [ ] wallet backup directories
  - [ ] secret env files
- [x] Generate archive filenames internally.
- [x] Do not use LLM-provided strings as raw output path components.
- [x] Store original source path only if safe.

## 8.3 Tests

- [x] Accept file under approved workspace.
- [x] Reject `/etc/passwd`.
- [x] Reject Bitcoin datadir path.
- [x] Reject `../` escape.
- [x] Reject symlink to outside workspace.
- [x] Reject directory.
- [x] Reject oversized file.
- [x] Refuse overwrite.
- [x] Archived output remains under archive root.
- [x] Metadata records hash.

---

# 9. P1 — Tighten `PURCHASE` Policy Semantics

## 9.1 Problem

The workflow uses `ActionType.PURCHASE` for initial review/planning of paid opportunities, but strict spend prerequisites may only apply to `SPEND` and `WALLET_TRANSFER`.

## 9.2 Required Decision

Choose one:

### Option A — `PURCHASE` means real executable purchase

Then:

- [x] Treat `PURCHASE` as money-risky.
- [x] Require TOS/legal approval.
- [x] Require budget plan.
- [x] Require policy approval.
- [x] Require ledger prewrite.
- [x] Require wallet-governor path.
- [x] Reject purchase without all spend prerequisites.

### Option B — Initial review is not `PURCHASE`

Then:

- [x] Replace initial review action with `RESEARCH` or `OPPORTUNITY_ANALYSIS`.
- [x] Set `requires_payment=False`.
- [x] Set `requires_wallet_action=False`.
- [x] Reserve `PURCHASE` for real executable purchase.

Recommended: **Option B for initial opportunity review, Option A for actual purchase.**

## 9.3 Tests

- [x] Initial opportunity analysis does not use executable purchase semantics.
- [x] `PURCHASE` without budget is blocked.
- [x] `PURCHASE` without TOS/legal proceed is blocked.
- [x] `PURCHASE` without ledger prewrite is blocked.
- [x] Executable purchase uses same gates as wallet spend.

---

# 10. P1 — Fix Wallet Quote Fee Accounting

## 10.1 Problem

Quote currently reports total USD as request amount and may report fee USD as zero even when fee BTC exists.

## 10.2 Required Fix

- [x] Add `fee_btc` to quote response if not already present.
- [x] Add `estimated_fee_usd`.
- [x] Add `total_usd_estimate`.
- [x] Define exchange-rate input/source.
- [x] For fake backend, use configured static BTC/USD rate.
- [x] For real backend, use configured rate source or explicitly require caller-supplied rate.
- [x] Do not silently report zero fee USD when fee exists.
- [x] Document whether limits apply to amount only or amount plus fee.
- [x] Recommended: limits should apply to amount plus estimated fee.

## 10.3 Tests

- [x] Quote includes fee BTC.
- [x] Quote includes estimated fee USD.
- [x] Quote includes total USD estimate.
- [x] Total USD estimate equals amount plus fee.
- [x] Fee-inclusive single limit rejection works.
- [x] Fee-inclusive daily limit rejection works.
- [x] Fee-inclusive weekly limit rejection works.

---

# 11. P1 — Harden Policy Guard

## 11.1 Expand Blocked Taxonomy

Ensure policy guard blocks:

- [x] gambling
- [x] prediction markets
- [x] securities trading
- [x] options trading
- [x] forex trading
- [x] futures trading
- [x] leveraged products
- [x] autonomous crypto trading
- [x] DeFi yield farming
- [x] NFT speculation
- [x] token speculation
- [x] airdrop farming
- [x] fake accounts
- [x] account farming
- [x] KYC evasion
- [x] fake reviews
- [x] spam
- [x] phishing
- [x] malware
- [x] credential harvesting
- [x] scraping against terms
- [x] paywall bypass
- [x] money transmission
- [x] escrow
- [x] exchange/broker behavior
- [x] mixing/tumbling
- [x] handling other people's funds
- [x] impersonation
- [x] deceptive claims
- [x] hidden affiliate/referral abuse

## 11.2 Enforce Workflow Prerequisites

- [x] Money-risky actions require budget reference.
- [x] Money-risky actions require TOS/legal reference.
- [x] Money-risky actions require ledger reference.
- [x] Email send actions require approved opportunity/experiment reference.
- [x] Browser submit actions require approved opportunity/experiment reference.
- [x] Account creation requires bot-owned account context.
- [x] Unknown executable actions return `needs_review` or `block`.
- [x] High-risk financial actions return `block`.

## 11.3 Tests

- [x] Add blocked fixture for every prohibited category.
- [x] Test unknown category handling.
- [x] Test missing budget reference.
- [x] Test missing TOS/legal reference.
- [x] Test missing ledger reference.
- [x] Test allowed safe research.
- [x] Test allowed draft-only email.
- [x] Test blocked spam.
- [x] Test blocked fake review.
- [x] Test blocked wallet secret/tool access.

---

# 12. P1 — Improve TOS/Legal Checker

## 12.1 Required Enhancements

- [x] Require source evidence.
- [x] Store source URL.
- [x] Store evidence artifact IDs.
- [x] Extract relevant snippets.
- [x] Label snippets by risk type.
- [x] Classify automation as allowed/prohibited/unclear.
- [x] Classify bot accounts as allowed/prohibited/unclear.
- [x] Classify payment rules as clear/unclear.
- [x] Classify eligibility requirements as clear/unclear.
- [x] Classify identity/KYC requirements.
- [x] Classify recurring billing.
- [x] Classify refund/chargeback risk.
- [x] Classify outreach/scraping restrictions.
- [x] Classify third-party funds risk.
- [x] Return `human_review` if rules are missing or unclear.
- [x] Return `reject` if automation or bot use is prohibited.
- [x] Return `reject` or `human_review` for regulated financial activity.
- [x] Link TOS/legal result to opportunity and evidence records.

## 12.2 Tests

- [x] Missing terms returns `human_review`.
- [x] No-bots language returns `reject`.
- [x] Fake-account language returns `reject`.
- [x] Unclear payment returns `human_review`.
- [x] Clear bounty rules return `proceed`.
- [x] Third-party funds returns `reject`.
- [x] Identity verification returns `human_review`.
- [x] Recurring billing returns `human_review`.
- [x] Snippets are stored.
- [x] Evidence artifact IDs are required.

---

# 13. P1 — Improve Budget and ROI Planner

## 13.1 Required Enhancements

- [x] Require policy decision reference.
- [x] Require policy decision exactly `allow`.
- [x] Require TOS/legal decision reference.
- [x] Require TOS/legal decision exactly `proceed`.
- [x] Require explicit spend amount.
- [x] Require explicit maximum loss.
- [x] Require expected revenue or explicit unknown revenue flag.
- [x] Require success metric.
- [x] Require stop condition.
- [x] Require break-even condition for nonzero spend.
- [x] Account for wallet/network fees.
- [x] Account for platform fees.
- [x] Account for recurring costs.
- [x] Account for estimated time cost, even if not monetized.
- [x] Reject if worst-case loss exceeds budget.
- [x] Reject if recurring costs are uncapped.
- [x] Return `simulate` when economics are too uncertain.
- [x] Return `reject` when expected loss is too high or terms are unclear.

## 13.2 Wallet Handoff Fields

Budget plan should expose:

- [x] wallet spend allowed flag
- [x] max wallet spend amount
- [x] approved spend categories
- [x] related policy decision ID
- [x] related TOS/legal check ID
- [x] related opportunity ID
- [x] required evidence IDs
- [x] stop condition

## 13.3 Tests

- [x] Reject when policy is not `allow`.
- [x] Reject when TOS is not `proceed`.
- [x] Reject when spend exceeds max loss.
- [x] Reject recurring cost with no cap.
- [x] Return simulate when revenue is uncertain.
- [x] Return execute when all fields are valid and risk is low.
- [x] Test break-even calculation.
- [x] Test platform fee calculation.
- [x] Test wallet fee calculation.
- [x] Test ledger record creation.

---

# 14. P1 — Strengthen Ledger

## 14.1 Required Enhancements

- [x] Fix weekly spend SQL.
- [x] Add explicit spend status update method if missing.
- [x] Add transaction status update method if missing.
- [x] Add audit records for wallet rejections.
- [x] Add audit records for wallet backend failures.
- [x] Add method to fetch full spend authorization bundle:
  - [ ] spend request
  - [ ] policy decision
  - [ ] budget plan
  - [ ] TOS/legal check
  - [ ] opportunity
  - [ ] evidence artifacts
  - [ ] prior wallet transactions
- [x] Add method to calculate remaining daily limit.
- [x] Add method to calculate remaining weekly limit.
- [x] Add method to calculate experiment spend total.
- [x] Add method to calculate spend by category.
- [x] Add migration/version tracking if missing.
- [x] Ensure foreign keys are enabled on every SQLite connection.
- [x] Ensure raw JSON round-trips.

## 14.2 Tests

- [x] Fetch full authorization bundle.
- [x] Spend status transitions.
- [x] Wallet transaction links to spend request.
- [x] Daily limit calculation.
- [x] Weekly limit calculation.
- [x] Experiment spend calculation.
- [x] Rejected spend audit.
- [x] Failed backend audit.
- [x] Hash chain remains valid.
- [x] Raw JSON round-trips.

---

# 15. P1 — Improve Evidence Archiver

## 15.1 Required Enhancements

- [x] Add workspace allowlist for file reads.
- [x] Enforce max file size.
- [x] Enforce safe output paths.
- [x] Prevent overwrite.
- [x] Store hash.
- [x] Store artifact metadata.
- [x] Store source URL where applicable.
- [x] Store artifact type.
- [x] Link artifact to ledger record.
- [x] Redact obvious secrets from text artifacts if redaction is enabled.
- [x] Never archive wallet passphrases.
- [x] Never archive key material.
- [x] Never archive `.ssh` keys.
- [x] Never archive Bitcoin Core wallet files.
- [x] Never archive browser cookie stores.

## 15.2 Tests

- [x] Text artifact archive.
- [x] Binary artifact archive.
- [x] Metadata JSON creation.
- [x] Hash matches content.
- [x] Ledger artifact record creation.
- [x] Path traversal rejection.
- [x] Symlink escape rejection.
- [x] Sensitive path rejection.
- [x] Max file size rejection.
- [x] Overwrite rejection.

---

# 16. P1 — Improve Email Drafter While Keeping Draft-Only Mode

## 16.1 Required Work

- [x] Confirm email mode defaults to `draft_only`.
- [x] Confirm no SMTP/API sending path is active by default.
- [x] Ensure all email drafts link to opportunity or experiment.
- [x] Ensure all email drafts are recorded in ledger.
- [x] Ensure all email drafts are archived as evidence.
- [x] Require truthful subject.
- [x] Block fake identity.
- [x] Block fake affiliation.
- [x] Block fake urgency.
- [x] Block deceptive claims.
- [x] Block bulk outreach.
- [x] Block scraped recipient lists.
- [x] Block harassment/follow-up loops.
- [x] Include bot/automation disclosure where appropriate.
- [x] Add compliance flags:
  - [ ] commercial outreach
  - [ ] cold outreach
  - [ ] affiliate/referral content
  - [ ] bounty submission
  - [ ] support request

## 16.2 Tests

- [x] Draft-only output.
- [x] Fake identity blocked.
- [x] Deceptive subject blocked.
- [x] Spam-like body blocked.
- [x] Missing opportunity/experiment reference rejected.
- [x] Draft written to ledger.
- [x] Draft archived as evidence.
- [x] Automation disclosure included when configured.

---

# 17. P1 — Improve Experiment Reviewer

## 17.1 Required Work

- [x] Ensure reviewer reads ledger records for the experiment.
- [x] Include spend requests.
- [x] Include wallet transactions.
- [x] Include email drafts/events.
- [x] Include evidence artifacts.
- [x] Include policy decisions.
- [x] Include TOS/legal checks.
- [x] Include budget plans.
- [x] Calculate gross spend.
- [x] Calculate fees.
- [x] Calculate revenue.
- [x] Calculate net.
- [x] Calculate ROI.
- [x] Track estimated time if available.
- [x] Identify policy block incidents.
- [x] Identify failed spend incidents.
- [x] Identify rejected spend incidents.
- [x] Identify missing evidence incidents.
- [x] Identify no-response outcomes.
- [x] Identify stop-condition trigger.
- [x] Recommend `continue`, `stop`, `retry_with_changes`, or `block_category`.
- [x] Store review in ledger.
- [x] Archive review summary.

## 17.2 Tests

- [x] Profitable experiment review.
- [x] Losing experiment review.
- [x] No-spend experiment review.
- [x] Failed wallet spend review.
- [x] Missing evidence review.
- [x] Repeated failure leads to block-category recommendation.
- [x] Review record stored in ledger.
- [x] Review summary archived.

---

# 18. P2 — Add Real Opportunity Source Adapters

## 18.1 Current Limitation

Opportunity scout evaluates supplied source documents. It does not yet scout actual sources.

## 18.2 Adapter Interface

Create a common adapter interface:

```text
OpportunitySourceAdapter
  fetch_candidates()
  normalize_candidate()
  attach_source_evidence()
```

## 18.3 Initial Adapters

- [x] Local fixture/document adapter.
- [x] Manual URL ingestion adapter.
- [x] GitHub issue/search adapter using fixture-based tests.
- [x] Public bounty page adapter.
- [x] Hackathon/contest listing adapter.

Do not add broad autonomous browsing until P0/P1 safety work is done.

## 18.4 Candidate Fields

Each candidate should include:

- [x] title/name
- [x] source URL
- [x] source type
- [x] description
- [x] required spend estimate
- [x] expected payout/revenue estimate
- [x] maximum loss estimate
- [x] deadline
- [x] payment method, if known
- [x] eligibility requirements, if known
- [x] evidence artifact IDs
- [x] red flags
- [x] recommended next step

## 18.5 Tests

- [x] Local fixture adapter.
- [x] Manual URL adapter with supplied HTML/text.
- [x] GitHub adapter using fixture JSON, not live network.
- [x] Deduplication.
- [x] Prohibited category rejection.
- [x] Missing payout handled as lower confidence or review.
- [x] Candidate evidence archived.

---

# 19. P2 — Documentation Updates

## 19.1 Required Docs

Add or update:

- [x] `docs/SAFETY_INVARIANTS.md`
- [x] `docs/WALLET_GOVERNOR_DESIGN.md`
- [x] `docs/LEDGER_SCHEMA.md`
- [x] `docs/EVIDENCE_ARCHIVE.md`
- [x] `docs/LOCAL_DEPLOYMENT.md`
- [x] `docs/TESTING.md`
- [x] `docs/CODE_REVIEW1_FIXES.md`

## 19.2 README Updates

- [x] Explain project purpose.
- [x] Explain that real spend is disabled by default.
- [x] Explain local LLM assumption.
- [x] Explain wallet-governor architecture.
- [x] Explain ledger and evidence archive.
- [x] Explain how to run tests.
- [x] Explain how to run dry-run workflow.
- [x] Explain current limitations.
- [x] Explain not to connect real BTC until P0 is complete.
- [x] Include branch assumption that both agents start from Copilot base.

---

# 20. P2 — Test Suite Cleanup

## 20.1 Python Version Test

Problem:

```text
test_python_version_is_311
```

fails in Python 3.13 review environments.

Fix options:

- [x] Enforce Python 3.11 through `pyproject.toml` / `uv`.
- [ ] Convert the test to skip unless running in strict CI.
- [ ] Convert hard failure into clear environment warning.
- [x] Document Python version requirement.

Recommended:

```text
Keep project pinned to Python 3.11 if desired, but do not make normal review impossible under newer Python unless CI explicitly requires it.
```

## 20.2 Add Safety Regression Fixtures

Create fixtures for:

- [x] crypto trading proposal
- [x] prediction market proposal
- [x] gambling proposal
- [x] fake review proposal
- [x] spam outreach proposal
- [x] KYC evasion proposal
- [x] money transmission proposal
- [x] scraping-against-terms proposal
- [x] malware proposal
- [x] credential theft proposal
- [x] handling third-party funds proposal
- [x] send-all wallet proposal
- [x] missing ledger prewrite spend proposal
- [x] TOS `human_review` spend proposal
- [x] blocked category spend proposal

Each fixture must be blocked by the appropriate layer.

---

# 21. P3 — Optional Browser Governor Later

Do not implement browser automation until wallet/ledger/policy/evidence safety is stable.

Future requirements:

- [x] Bot-owned browser profile only.
- [x] No personal accounts.
- [x] No KYC flows without human review.
- [x] No CAPTCHA bypass.
- [x] No bot-evasion behavior.
- [x] No mass signup.
- [x] No scraping against terms.
- [x] No purchases outside wallet-governor flow.
- [x] Ledger record before form submission.
- [x] Evidence archive before and after form submission.
- [x] Policy check before every submit/post/purchase action.

---

# 22. P3 — Optional Email Governor Later

Do not enable sending yet.

Future requirements:

- [x] Dedicated bot email account only.
- [x] No personal email.
- [x] No imported personal contacts.
- [x] Daily rate limit.
- [x] Per-domain rate limit.
- [x] Follow-up limit per thread.
- [x] Policy approval before send.
- [x] Ledger record before send.
- [x] Evidence archive after send.
- [x] Incoming reply classification.
- [x] Opt-out handling if cold commercial outreach is used.
- [x] No bulk outreach.
- [x] No scraped lists.
- [x] No deceptive headers/subjects/body.

---

# 23. Suggested Work Split Between Copilot and OpenCode

Because both branches now start from Copilot's code, split work by module instead of by old implementation.

## 23.1 Suggested Copilot Assignment

Copilot should focus on:

- [ ] P0 wallet-governor service authorization.
- [ ] P0 wallet client TOS bug.
- [ ] P0 weekly spend SQL.
- [ ] P0 ledger responsibility refactor.
- [ ] P0 audit durability.
- [ ] Tests for all P0 wallet safety paths.

## 23.2 Suggested OpenCode Assignment

OpenCode should focus on:

- [ ] Evidence archive path restrictions.
- [ ] Policy guard taxonomy expansion.
- [ ] TOS/legal checker improvements.
- [ ] Budget planner improvements.
- [ ] Documentation updates.
- [ ] Additional safety regression fixtures.

## 23.3 Integration Rule

- [ ] Do not let both agents edit the same file at the same time unless one branch is clearly authoritative.
- [ ] Merge P0 wallet changes first.
- [ ] Re-run full tests after each major merge.
- [ ] Do not enable spend until P0 tests pass.

---

# 24. Final Acceptance Criteria for This TODO

This TODO is complete when:

- [ ] OpenCode branch has been reset to Copilot branch head.
- [x] All P0 wallet-governor service checks are implemented.
- [x] Wallet client blocks TOS `human_review`.
- [x] Weekly spend SQL is fixed and tested.
- [x] Client/service spend ledger responsibilities are clean.
- [x] Spend rejections are durable and auditable.
- [x] Evidence archiver cannot read arbitrary local paths.
- [x] Policy guard blocks all prohibited categories.
- [x] TOS/legal checker returns `human_review` for unclear terms.
- [x] Budget planner requires explicit spend, max loss, success metric, and stop condition.
- [x] Email remains draft-only.
- [x] Real wallet backend is either absent or disabled by default.
- [x] If Bitcoin Core backend exists, it is disabled by default and tested with fake RPC only.
- [x] Full test suite passes.
- [x] Safety regression fixtures pass.
- [x] README and safety docs explain that real BTC must not be connected until these checks pass.

---

# 25. Final Note

The immediate goal is not to make the bot more autonomous.

The immediate goal is to make the existing Copilot implementation **safe, internally consistent, auditable, and difficult to bypass**.

Only after the P0/P1 work is complete should the project move toward real Bitcoin Core integration, browser automation, email sending, or live opportunity scouting.
