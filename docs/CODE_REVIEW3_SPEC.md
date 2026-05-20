# CODE_REVIEW3_SPEC.md

# OpenClaw MoneyBot — Code Review 3 Remediation Specification

## 1. Purpose

This specification defines the third remediation pass for the latest Copilot implementation of `openclaw_moneybot`.

The previous implementation pass resolved nearly all Code Review 2 issues:

- Policy action metadata is persisted and read back.
- Wallet service rejects non-executable policy approvals.
- Wallet service rejects request/ledger mismatches.
- Spend-disabled rejections update eligible spend requests.
- Budget planner decision precedence is fixed.
- Missing budget references no longer crash with SQLite FK errors.
- Evidence `content_text` size limits are enforced.
- Evidence type sanitization is stronger.
- Wallet service verifies evidence file paths and hashes.
- Ledger spend summary APIs exist.
- Tests passed in review: `296 passed`.

However, the latest review still found several issues that must be fixed before real BTC can be connected.

## 2. Current Readiness

Current status after Code Review 2 implementation:

```text
Dry-run readiness: good
Mock-wallet readiness: good
Real hot-wallet readiness: not yet
```

The next implementation pass must preserve all current safety defaults:

- Real wallet spending disabled by default.
- Bitcoin Core backend disabled by default.
- Email sending disabled by default.
- Browser automation disabled/non-executing by default.
- No arbitrary Bitcoin RPC passthrough.
- No wallet secrets in repo, tests, fixtures, prompts, logs, or docs.

## 3. Main Remaining Issues

The latest review found these remaining issues:

```text
P0:
- Bitcoin destination validation is only prefix/length based.
- Address validation is not network-aware enough for mainnet/testnet/regtest safety.
- Configured destination blocklist support is missing.
- Wallet client quote handling crashes on rejected quote responses.
- Backend balance failure in capped_send() lacks an explicit backend-failure audit event.

P1:
- Wallet service does not enforce allowed evidence artifact types for spend authorization.
- Ledger BTC accounting aggregates BTC strings/floats instead of exact integer satoshis.
```

## 4. Primary Goal

The primary goal is to make wallet destination validation and quote handling strong enough that the service will not approve, quote, or fake-send to malformed Bitcoin-looking strings.

The secondary goal is to improve spend evidence validation and BTC accounting precision.

## 5. Required Safety Invariants

After this remediation pass, the implementation must enforce the following.

### 5.1 Bitcoin Address Validation Invariants

A BTC destination must not be considered valid unless:

1. It is syntactically valid for the configured Bitcoin network.
2. It passes real checksum validation.
3. It contains only characters valid for its encoding.
4. It is not a placeholder/test/example string.
5. It is not a send-all/sweep/max/all-funds instruction.
6. It is not present in the configured destination blocklist.
7. It is accepted only on the configured network:
   - mainnet accepts mainnet addresses only
   - testnet accepts testnet addresses only
   - regtest accepts regtest addresses only, if supported
8. It is validated in both quote and send paths.
9. The fake backend path uses the same validation logic as real backend preflight.
10. The Bitcoin Core backend must either perform local validation before RPC or use `validateaddress` defensively and reject invalid/non-matching-network addresses before send.

### 5.2 Quote Handling Invariants

The wallet client must not assume every quote response is successful.

It must:

1. Inspect quote response status before reading amount fields.
2. Return a structured rejected/error result when the service rejects a quote.
3. Preserve rejection reason codes.
4. Avoid `KeyError` or unhandled exceptions for valid rejected quote responses.
5. Avoid treating rejected quotes as spendable/sendable.

### 5.3 Backend Failure Audit Invariants

All backend failures during `capped_send()` must produce durable audit records.

This includes:

- balance lookup failure
- fee estimation failure
- unlock failure
- send failure
- lock failure

A backend balance failure must not only update the spend status; it must also write a clear audit event.

### 5.4 Evidence Type Invariants

For wallet-spend authorization, evidence artifacts must not only exist and hash-match. They must also be of an acceptable type for spend authorization.

The service must reject irrelevant artifact types such as:

```text
random_note
scratchpad
unrelated_log
debug_dump
```

Allowed spend-evidence types must be explicitly configured or defined.

### 5.5 BTC Accounting Invariants

Ledger BTC accounting must avoid floating-point aggregation for spend summaries.

Long-term behavior should prefer integer satoshis.

At minimum:

- wallet transaction records should store exact satoshi amounts and fee satoshis, or
- summary APIs must convert BTC strings to integer satoshis safely before aggregation.

Avoid:

```text
CAST(amount_btc AS REAL)
floating-point BTC summation
lossy decimal math
```

## 6. Required Architecture Changes

## 6.1 Real Bitcoin Address Validation

Replace prefix/length destination validation with real validation.

### Acceptable Implementation Options

One of these approaches is acceptable:

#### Option A — Local pure-Python validation

Implement deterministic local validation for:

- Bech32 / Bech32m addresses
- Base58Check P2PKH/P2SH addresses
- network/version-byte checking
- character-set checking
- checksum checking

#### Option B — Dependency-based validation

Use a well-maintained library that supports:

- mainnet/testnet/regtest detection
- Base58Check validation
- Bech32/Bech32m validation
- checksum validation

The dependency must be added explicitly to project metadata and tests must cover behavior.

#### Option C — Bitcoin Core validation for real backend plus local fake-mode validator

Use local validation for fake/mock mode and `validateaddress` defensively for real Bitcoin Core mode.

Even if `validateaddress` is used, do not send raw invalid addresses to `sendtoaddress`.

### Required Network Modes

Support at least:

```text
mainnet
testnet
regtest
```

If signet is already supported or easy to add, it may be included, but it is not required for this pass.

## 6.2 Destination Blocklist

Add configured destination blocklist support.

The blocklist should apply to both quote and send paths.

The blocklist should support exact address matches at minimum.

Optional future enhancements:

- labels
- reason text
- prefix blocking
- regex blocking

For this pass, exact match is sufficient.

## 6.3 Wallet Client Quote Result Handling

Modify the wallet client quote path so that a rejected quote response does not crash.

The client should return a typed result that can represent:

```text
ok
rejected
error
```

For rejected responses, it should preserve:

- rejection reason
- rejection reasons list
- service status
- sanitized raw response if currently stored

## 6.4 Backend Balance Failure Auditing

In `WalletGovernorService.capped_send()` or equivalent, wrap balance lookup failures and record explicit audit events.

Suggested audit event type:

```text
wallet_backend_balance_failed
```

or:

```text
wallet_backend_failure
```

The audit event must include:

- spend_request_id
- idempotency_key
- reason code
- sanitized request summary
- backend mode if safe
- no secrets

## 6.5 Allowed Spend Evidence Types

Add a defined allowlist for artifact types that can satisfy wallet-spend evidence requirements.

Suggested allowed types:

```text
terms_snapshot
tos_snapshot
receipt
invoice
html_snapshot
wallet_governor_response
budget_snapshot
policy_snapshot
opportunity_snapshot
submission_receipt
payment_request
```

The exact list may be adjusted, but it must be explicit.

The wallet service should reject required spend evidence if the artifact type is not in the allowlist.

## 6.6 Integer Satoshi Accounting

Add or migrate toward satoshi-denominated storage and aggregation.

Recommended:

- keep existing BTC string fields for compatibility/display if needed
- add `amount_sats`
- add `fee_sats`
- use integer sat fields in summary APIs
- compute decimal BTC display from integer sats at the boundary

If a schema migration is needed, add one.

## 7. Non-Goals for This Pass

Do not implement:

- real wallet spending enabled by default
- real email sending enabled by default
- real browser automation
- unrestricted shell execution
- exchange APIs
- DeFi integrations
- Solana/EVM wallet integrations
- arbitrary Bitcoin RPC passthrough
- sweeping/send-all behavior
- production deployment scripts that auto-enable spending

## 8. Required Tests

The final implementation must include tests for:

- invalid Bech32-looking address rejected
- invalid Base58-looking address rejected
- address with spaces rejected
- address with punctuation rejected
- valid mainnet Bech32 accepted on mainnet
- valid mainnet Base58 accepted on mainnet
- valid testnet address rejected on mainnet
- valid mainnet address rejected on testnet
- valid regtest address accepted on regtest, if regtest supported
- quote rejects all malformed BTC-looking strings
- send rejects all malformed BTC-looking strings
- configured blocklisted destination rejected in quote
- configured blocklisted destination rejected in send
- wallet client quote handles rejected service response without `KeyError`
- wallet client quote preserves rejection reasons
- backend balance failure writes audit event
- backend balance failure updates spend status correctly
- disallowed evidence artifact type rejects spend
- allowed evidence artifact type permits spend when all other gates pass
- ledger summary APIs aggregate integer sats exactly
- no floating-point BTC aggregation in spend summary paths

## 9. Acceptance Criteria

This pass is complete when:

- BTC destination validation is real and checksum-aware.
- BTC destination validation is network-aware.
- Quote and send paths share destination validation.
- Destination blocklist exists and is enforced.
- Wallet client handles rejected quote responses gracefully.
- Backend balance failures produce explicit durable audit events.
- Wallet service enforces allowed spend-evidence artifact types.
- Ledger spend summary APIs avoid float BTC aggregation.
- Full test suite passes.
- Real spend remains disabled by default.
- Bitcoin Core backend remains disabled by default.
- No secrets are committed.
- No arbitrary Bitcoin RPC passthrough exists.

## 10. Final Rule

Do not connect real BTC until this spec and `CODE_REVIEW3_TODO.md` are implemented and reviewed.
