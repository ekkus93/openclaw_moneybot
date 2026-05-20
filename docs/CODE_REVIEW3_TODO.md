# CODE_REVIEW3_TODO.md

# OpenClaw MoneyBot — Code Review 3 TODO

This TODO is based on the review of the latest Copilot implementation after `CODE_REVIEW2_TODO.md`.

The latest implementation passed tests, but a few issues remain before real BTC can be connected.

## Priority Legend

```text
P0 = must fix before any real wallet connection or real spend
P1 = must fix before serious autonomous operation
P2 = cleanup / documentation / hardening
```

---

# 0. Global Rules

- [x] Continue from the latest Copilot implementation reviewed after Code Review 2.
- [x] Keep real wallet spending disabled by default.
- [x] Keep Bitcoin Core backend disabled by default.
- [x] Keep email sending disabled by default.
- [x] Keep browser automation non-executing/disabled by default.
- [x] Do not add arbitrary Bitcoin RPC passthrough.
- [x] Do not add `sendall`, `dumpprivkey`, `dumpwallet`, or equivalent wallet methods.
- [x] Do not commit wallet passphrases.
- [x] Do not commit private keys.
- [x] Do not commit Bitcoin Core RPC cookies.
- [x] Do not commit seed phrases.
- [x] Do not put secrets in tests, fixtures, logs, prompts, or docs.
- [x] Fail closed on malformed, missing, ambiguous, or unverifiable data.
- [x] Add regression tests for every fixed issue.
- [x] Run the full test suite before completion.

---

# 1. P0 — Replace Prefix/Length BTC Address Validation

## 1.1 Problem

Current BTC validation is only prefix/length based. It rejects `not-a-btc-address`, but accepts malformed Bitcoin-looking strings such as:

```text
bc1notvalid!!!!
bc1 bad space addr
1notvalid$$$$$$$
tb1bad address with space
```

This is not safe for real wallet use.

## 1.2 Required Behavior

Replace the existing BTC address validation with real validation.

The validator must reject:

- [x] malformed Bech32-looking addresses
- [x] malformed Bech32m-looking addresses
- [x] malformed Base58Check-looking addresses
- [x] addresses with invalid checksum
- [x] addresses with invalid characters
- [x] addresses containing spaces
- [x] addresses containing punctuation not valid for their encoding
- [x] placeholder strings
- [x] send-all/sweep/max/all-funds instructions
- [x] unsupported-network addresses

The validator must accept valid addresses for the configured network.

## 1.3 Implementation Options

Choose one:

### Option A — Pure Python Local Validator

- [x] Implement Bech32/Bech32m checksum validation.
- [x] Implement Base58Check checksum validation.
- [x] Implement network/version-byte checks.
- [x] Implement regtest/testnet/mainnet HRP checks.
- [x] Add tests with known valid and invalid addresses.

### Option B — Library Validator

- [x] Select a well-maintained Bitcoin address validation library.
- [x] Add dependency to project metadata.
- [x] Ensure dependency works in Python 3.11.
- [x] Wrap library errors in fail-closed validation result.
- [x] Add tests with known valid and invalid addresses.

### Option C — Hybrid Validator

- [x] Use local validation for fake/mock mode.
- [x] Use Bitcoin Core `validateaddress` defensively in real backend mode.
- [x] Still reject invalid addresses before `sendtoaddress`.

## 1.4 Required API

Create a centralized helper, for example:

```text
validate_btc_address(address: str, network: BitcoinNetwork) -> AddressValidationResult
```

The result should include:

- [x] `is_valid`
- [x] `network`
- [x] `address_type`, if known
- [x] `reason_code`, if invalid
- [x] `normalized_address`, if applicable

## 1.5 Required Tests

- [x] Reject `bc1notvalid!!!!`.
- [x] Reject `bc1 bad space addr`.
- [x] Reject `1notvalid$$$$$$$`.
- [x] Reject `tb1bad address with space`.
- [x] Reject address with invalid Bech32 checksum.
- [x] Reject address with invalid Base58Check checksum.
- [x] Reject mixed-case Bech32 address if invalid.
- [x] Reject empty string.
- [x] Reject placeholder string.
- [x] Accept valid mainnet Bech32 address.
- [x] Accept valid mainnet Base58 P2PKH address.
- [x] Accept valid mainnet Base58 P2SH address.
- [x] Accept valid testnet Bech32 address.
- [x] Accept valid testnet Base58 address.
- [x] Accept valid regtest Bech32 address if regtest is supported.
- [x] Validator returns reason codes for invalid cases.

---

# 2. P0 — Make BTC Address Validation Network-Aware

## 2.1 Problem

Address validation must not merely prove that an address is syntactically valid. It must prove that the address belongs to the configured network.

## 2.2 Required Networks

Support:

- [x] mainnet
- [x] testnet
- [x] regtest

Optional:

- [x] signet

## 2.3 Required Behavior

- [x] Mainnet mode accepts mainnet addresses only.
- [x] Mainnet mode rejects testnet addresses.
- [x] Mainnet mode rejects regtest addresses.
- [x] Testnet mode accepts testnet addresses only.
- [x] Testnet mode rejects mainnet addresses.
- [x] Regtest mode accepts regtest addresses only.
- [x] Regtest mode rejects mainnet addresses.
- [x] Regtest mode rejects testnet addresses unless explicitly documented as acceptable.
- [x] Unknown network config fails closed.

## 2.4 Integration Points

Apply network-aware validation in:

- [x] wallet-governor quote path
- [x] wallet-governor send path
- [x] wallet client preflight, if client validates destinations
- [x] Bitcoin Core backend preflight
- [x] tests and fixtures

## 2.5 Required Tests

- [x] Mainnet service accepts valid mainnet Bech32.
- [x] Mainnet service accepts valid mainnet Base58.
- [x] Mainnet service rejects valid testnet address.
- [x] Mainnet service rejects valid regtest address.
- [x] Testnet service accepts valid testnet Bech32.
- [x] Testnet service accepts valid testnet Base58.
- [x] Testnet service rejects valid mainnet address.
- [x] Regtest service accepts valid regtest Bech32.
- [x] Regtest service rejects valid mainnet address.
- [x] Unknown network config rejects quote/send.

---

# 3. P0 — Enforce Destination Blocklist

## 3.1 Problem

The TODO required configured destination blocklist support, but the latest reviewed implementation did not appear to include a destination blocklist.

## 3.2 Required Config

Add a wallet-governor config field:

```text
blocked_destinations: list[str]
```

Optional but useful:

```text
blocked_destination_labels: dict[str, str]
```

## 3.3 Required Behavior

- [x] Exact address matches are blocked.
- [x] Blocklist is checked after normalization, if normalization exists.
- [x] Blocklist applies to quote.
- [x] Blocklist applies to send.
- [x] Blocklist rejection uses reason code `destination_blocked`.
- [x] Blocklist rejection writes audit event for send attempts.
- [x] Blocklist does not leak labels if labels contain sensitive notes.
- [x] Empty blocklist is allowed.

## 3.4 Required Tests

- [x] Quote rejects blocklisted destination.
- [x] Send rejects blocklisted destination.
- [x] Non-blocklisted valid destination is accepted.
- [x] Blocklisted destination rejection does not call backend.
- [x] Blocklisted destination rejection writes audit event on send.
- [x] Empty blocklist does not block valid destination.

---

# 4. P0 — Fix Wallet Client Quote Handling for Rejected Responses

## 4.1 Problem

The wallet service can now return structured rejected quote responses. The wallet client currently assumes successful quote response fields exist and can crash with `KeyError`.

Example rejected quote response:

```json
{
  "status": "rejected",
  "asset": "BTC",
  "amount_usd": 5.0,
  "reason": "destination_invalid",
  "rejection_reasons": ["destination_invalid"]
}
```

The client must not attempt to read `amount_btc` or `fee_btc` unless status is successful.

## 4.2 Required Behavior

In wallet client quote handling:

- [x] Inspect `status` before parsing successful quote fields.
- [x] If status is `rejected`, return a structured rejected result.
- [x] If status is `error`, return a structured error result.
- [x] Preserve `reason`.
- [x] Preserve `rejection_reasons`.
- [x] Do not raise `KeyError`.
- [x] Do not treat rejected quote as spendable.
- [x] Do not call send after rejected quote in any orchestration path.
- [x] Preserve sanitized raw response if that is part of existing result model.

## 4.3 Model Changes

If needed, update quote result model to include:

- [x] `status`
- [x] `reason`
- [x] `rejection_reasons`
- [x] optional `amount_btc`
- [x] optional `fee_btc`
- [x] optional `estimated_fee_usd`
- [x] optional `total_usd_estimate`

Successful fields should be optional or guarded by status.

## 4.4 Required Tests

- [x] Wallet client handles rejected quote without exception.
- [x] Wallet client preserves rejection reason.
- [x] Wallet client preserves rejection reasons list.
- [x] Wallet client handles error quote without exception.
- [x] Wallet client parses successful quote correctly.
- [x] Orchestration does not proceed to send after rejected quote.
- [x] Rejected quote result is fail-closed.

---

# 5. P0 — Add Explicit Audit Event for Backend Balance Failure

## 5.1 Problem

If `backend.get_balance_sats()` fails during `capped_send()`, the service updates spend status but does not write a specific backend-failure audit event.

## 5.2 Required Behavior

When backend balance lookup fails:

- [x] Catch the backend exception.
- [x] Return structured failure response.
- [x] Use reason code `backend_error` or `wallet_balance_failed`.
- [x] Update spend request status appropriately.
- [x] Write explicit audit event.
- [x] Do not call fee quote.
- [x] Do not call unlock.
- [x] Do not call send.
- [x] Do not record wallet transaction.
- [x] Do not leak backend secrets/details.

## 5.3 Suggested Audit Event

Use one of:

```text
wallet_backend_balance_failed
wallet_backend_failure
```

Audit payload should include:

- [x] spend_request_id
- [x] idempotency_key
- [x] reason code
- [x] backend mode if safe
- [x] sanitized request summary
- [x] no secrets

## 5.4 Required Tests

- [x] Backend balance failure returns structured failure.
- [x] Backend balance failure updates spend status.
- [x] Backend balance failure writes audit event.
- [x] Backend balance failure does not call fee quote.
- [x] Backend balance failure does not call unlock.
- [x] Backend balance failure does not call send.
- [x] Backend balance failure does not record wallet transaction.
- [x] Backend balance failure response does not leak secrets.

---

# 6. P1 — Enforce Allowed Evidence Artifact Types for Spend Authorization

## 6.1 Problem

Wallet service verifies evidence IDs, file paths, and hashes, but does not appear to verify that artifact types are acceptable for spend authorization.

## 6.2 Required Config / Constant

Define an explicit allowlist:

```text
allowed_spend_evidence_types:
  - terms_snapshot
  - tos_snapshot
  - receipt
  - invoice
  - html_snapshot
  - wallet_governor_response
  - budget_snapshot
  - policy_snapshot
  - opportunity_snapshot
  - submission_receipt
  - payment_request
```

The exact list may be adjusted, but it must be explicit.

## 6.3 Required Behavior

- [x] Wallet service checks evidence artifact type.
- [x] Reject spend evidence with type not in allowlist.
- [x] Rejection reason: `evidence_type_not_allowed`.
- [x] Rejection writes audit event.
- [x] Backend is not called after disallowed evidence type.
- [x] Allowlist is configurable or centrally defined.
- [x] Tests use both allowed and disallowed artifact types.

## 6.4 Required Tests

- [x] `terms_snapshot` accepted as spend evidence.
- [x] `receipt` accepted as spend evidence.
- [x] `invoice` accepted as spend evidence.
- [x] `payment_request` accepted as spend evidence.
- [x] `random_note` rejected as spend evidence.
- [x] `scratchpad` rejected as spend evidence.
- [x] `debug_dump` rejected as spend evidence.
- [x] Disallowed evidence type writes audit event.
- [x] Disallowed evidence type does not call backend.

---

# 7. P1 — Improve Ledger BTC Accounting with Integer Satoshis

## 7.1 Problem

Ledger spend summary APIs may aggregate BTC strings using floating-point conversion or SQL `CAST(... AS REAL)`. This is not ideal for money accounting.

## 7.2 Required Design

Prefer exact integer satoshi accounting.

Recommended fields:

```text
amount_sats
fee_sats
```

Keep existing BTC string fields for display/backward compatibility if useful.

## 7.3 Schema / Model Updates

- [x] Add `amount_sats` to wallet transaction record/model.
- [x] Add `fee_sats` to wallet transaction record/model.
- [x] Add migration if needed.
- [x] Populate sat fields when recording wallet transactions.
- [x] Validate consistency between BTC string and sat fields if both exist.
- [x] Avoid using float for internal BTC accounting.
- [x] Use integer sats in summary APIs.

## 7.4 Summary API Requirements

Update:

```text
get_experiment_spend_total(experiment_id)
get_spend_by_category(...)
```

They should:

- [x] sum `amount_sats`
- [x] sum `fee_sats`
- [x] return total sats
- [x] return fee sats
- [x] optionally return display BTC string/Decimal
- [x] return USD totals using decimal-safe values
- [x] avoid SQL `CAST(amount_btc AS REAL)` for BTC aggregation
- [x] count only actual spend statuses: `sent`, `confirmed`
- [x] exclude non-spend statuses

## 7.5 Required Tests

- [x] Recording transaction stores amount_sats.
- [x] Recording transaction stores fee_sats.
- [x] Summary total uses amount_sats.
- [x] Summary fee total uses fee_sats.
- [x] Tiny satoshi values aggregate exactly.
- [x] Multiple transactions aggregate exactly.
- [x] No floating-point rounding error in BTC summaries.
- [x] Proposed/rejected/failed/cancelled spends excluded.
- [x] Sent/confirmed spends included.
- [x] Category summaries use integer sats.
- [x] Existing tests still pass.

---

# 8. P2 — Add Code Review 3 Documentation

## 8.1 Required Files

Add:

- [x] `docs/CODE_REVIEW3_SPEC.md`
- [x] `docs/CODE_REVIEW3_TODO.md`
- [x] `docs/CODE_REVIEW3_FIXES.md`, after implementation

## 8.2 `CODE_REVIEW3_FIXES.md`

After implementation, include:

- [x] summary of fixed P0 issues
- [x] summary of fixed P1 issues
- [x] changed files
- [x] test command
- [x] test result summary
- [x] deferred work
- [x] safety notes
- [x] confirmation that real spend remains disabled by default
- [x] confirmation that Bitcoin Core backend remains disabled by default

---

# 9. P2 — Add Focused Regression Test File

Create a focused regression test file, for example:

```text
tests/test_code_review3_regressions.py
```

It should include direct tests for:

- [x] invalid BTC-looking quote destination rejected
- [x] invalid BTC-looking send destination rejected
- [x] network mismatch rejected
- [x] blocklisted destination rejected
- [x] rejected quote response does not crash client
- [x] balance failure audit event
- [x] disallowed evidence type rejected
- [x] satoshi aggregation exactness

---

# 10. Final Acceptance Criteria

This TODO is complete when:

- [x] BTC validation is checksum-aware.
- [x] BTC validation rejects malformed Bitcoin-looking strings.
- [x] BTC validation is network-aware.
- [x] Quote path uses real BTC validation.
- [x] Send path uses real BTC validation.
- [x] Destination blocklist exists and is enforced in quote.
- [x] Destination blocklist exists and is enforced in send.
- [x] Wallet client handles rejected quote responses without exception.
- [x] Backend balance failure writes explicit audit event.
- [x] Wallet service rejects disallowed spend-evidence artifact types.
- [x] Ledger BTC summary APIs use integer sats or otherwise avoid float BTC aggregation.
- [x] New regression tests cover every item above.
- [x] Full test suite passes.
- [x] Real wallet spending remains disabled by default.
- [x] Bitcoin Core backend remains disabled by default.
- [x] No secrets are committed.
- [x] No arbitrary Bitcoin RPC passthrough exists.

---

# 11. Final Instruction

Do not connect real BTC after this implementation pass until the resulting code has been reviewed again.
