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

- [ ] Continue from the latest Copilot implementation reviewed after Code Review 2.
- [ ] Keep real wallet spending disabled by default.
- [ ] Keep Bitcoin Core backend disabled by default.
- [ ] Keep email sending disabled by default.
- [ ] Keep browser automation non-executing/disabled by default.
- [ ] Do not add arbitrary Bitcoin RPC passthrough.
- [ ] Do not add `sendall`, `dumpprivkey`, `dumpwallet`, or equivalent wallet methods.
- [ ] Do not commit wallet passphrases.
- [ ] Do not commit private keys.
- [ ] Do not commit Bitcoin Core RPC cookies.
- [ ] Do not commit seed phrases.
- [ ] Do not put secrets in tests, fixtures, logs, prompts, or docs.
- [ ] Fail closed on malformed, missing, ambiguous, or unverifiable data.
- [ ] Add regression tests for every fixed issue.
- [ ] Run the full test suite before completion.

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

- [ ] malformed Bech32-looking addresses
- [ ] malformed Bech32m-looking addresses
- [ ] malformed Base58Check-looking addresses
- [ ] addresses with invalid checksum
- [ ] addresses with invalid characters
- [ ] addresses containing spaces
- [ ] addresses containing punctuation not valid for their encoding
- [ ] placeholder strings
- [ ] send-all/sweep/max/all-funds instructions
- [ ] unsupported-network addresses

The validator must accept valid addresses for the configured network.

## 1.3 Implementation Options

Choose one:

### Option A — Pure Python Local Validator

- [ ] Implement Bech32/Bech32m checksum validation.
- [ ] Implement Base58Check checksum validation.
- [ ] Implement network/version-byte checks.
- [ ] Implement regtest/testnet/mainnet HRP checks.
- [ ] Add tests with known valid and invalid addresses.

### Option B — Library Validator

- [ ] Select a well-maintained Bitcoin address validation library.
- [ ] Add dependency to project metadata.
- [ ] Ensure dependency works in Python 3.11.
- [ ] Wrap library errors in fail-closed validation result.
- [ ] Add tests with known valid and invalid addresses.

### Option C — Hybrid Validator

- [ ] Use local validation for fake/mock mode.
- [ ] Use Bitcoin Core `validateaddress` defensively in real backend mode.
- [ ] Still reject invalid addresses before `sendtoaddress`.

## 1.4 Required API

Create a centralized helper, for example:

```text
validate_btc_address(address: str, network: BitcoinNetwork) -> AddressValidationResult
```

The result should include:

- [ ] `is_valid`
- [ ] `network`
- [ ] `address_type`, if known
- [ ] `reason_code`, if invalid
- [ ] `normalized_address`, if applicable

## 1.5 Required Tests

- [ ] Reject `bc1notvalid!!!!`.
- [ ] Reject `bc1 bad space addr`.
- [ ] Reject `1notvalid$$$$$$$`.
- [ ] Reject `tb1bad address with space`.
- [ ] Reject address with invalid Bech32 checksum.
- [ ] Reject address with invalid Base58Check checksum.
- [ ] Reject mixed-case Bech32 address if invalid.
- [ ] Reject empty string.
- [ ] Reject placeholder string.
- [ ] Accept valid mainnet Bech32 address.
- [ ] Accept valid mainnet Base58 P2PKH address.
- [ ] Accept valid mainnet Base58 P2SH address.
- [ ] Accept valid testnet Bech32 address.
- [ ] Accept valid testnet Base58 address.
- [ ] Accept valid regtest Bech32 address if regtest is supported.
- [ ] Validator returns reason codes for invalid cases.

---

# 2. P0 — Make BTC Address Validation Network-Aware

## 2.1 Problem

Address validation must not merely prove that an address is syntactically valid. It must prove that the address belongs to the configured network.

## 2.2 Required Networks

Support:

- [ ] mainnet
- [ ] testnet
- [ ] regtest

Optional:

- [ ] signet

## 2.3 Required Behavior

- [ ] Mainnet mode accepts mainnet addresses only.
- [ ] Mainnet mode rejects testnet addresses.
- [ ] Mainnet mode rejects regtest addresses.
- [ ] Testnet mode accepts testnet addresses only.
- [ ] Testnet mode rejects mainnet addresses.
- [ ] Regtest mode accepts regtest addresses only.
- [ ] Regtest mode rejects mainnet addresses.
- [ ] Regtest mode rejects testnet addresses unless explicitly documented as acceptable.
- [ ] Unknown network config fails closed.

## 2.4 Integration Points

Apply network-aware validation in:

- [ ] wallet-governor quote path
- [ ] wallet-governor send path
- [ ] wallet client preflight, if client validates destinations
- [ ] Bitcoin Core backend preflight
- [ ] tests and fixtures

## 2.5 Required Tests

- [ ] Mainnet service accepts valid mainnet Bech32.
- [ ] Mainnet service accepts valid mainnet Base58.
- [ ] Mainnet service rejects valid testnet address.
- [ ] Mainnet service rejects valid regtest address.
- [ ] Testnet service accepts valid testnet Bech32.
- [ ] Testnet service accepts valid testnet Base58.
- [ ] Testnet service rejects valid mainnet address.
- [ ] Regtest service accepts valid regtest Bech32.
- [ ] Regtest service rejects valid mainnet address.
- [ ] Unknown network config rejects quote/send.

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

- [ ] Exact address matches are blocked.
- [ ] Blocklist is checked after normalization, if normalization exists.
- [ ] Blocklist applies to quote.
- [ ] Blocklist applies to send.
- [ ] Blocklist rejection uses reason code `destination_blocked`.
- [ ] Blocklist rejection writes audit event for send attempts.
- [ ] Blocklist does not leak labels if labels contain sensitive notes.
- [ ] Empty blocklist is allowed.

## 3.4 Required Tests

- [ ] Quote rejects blocklisted destination.
- [ ] Send rejects blocklisted destination.
- [ ] Non-blocklisted valid destination is accepted.
- [ ] Blocklisted destination rejection does not call backend.
- [ ] Blocklisted destination rejection writes audit event on send.
- [ ] Empty blocklist does not block valid destination.

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

- [ ] Inspect `status` before parsing successful quote fields.
- [ ] If status is `rejected`, return a structured rejected result.
- [ ] If status is `error`, return a structured error result.
- [ ] Preserve `reason`.
- [ ] Preserve `rejection_reasons`.
- [ ] Do not raise `KeyError`.
- [ ] Do not treat rejected quote as spendable.
- [ ] Do not call send after rejected quote in any orchestration path.
- [ ] Preserve sanitized raw response if that is part of existing result model.

## 4.3 Model Changes

If needed, update quote result model to include:

- [ ] `status`
- [ ] `reason`
- [ ] `rejection_reasons`
- [ ] optional `amount_btc`
- [ ] optional `fee_btc`
- [ ] optional `estimated_fee_usd`
- [ ] optional `total_usd_estimate`

Successful fields should be optional or guarded by status.

## 4.4 Required Tests

- [ ] Wallet client handles rejected quote without exception.
- [ ] Wallet client preserves rejection reason.
- [ ] Wallet client preserves rejection reasons list.
- [ ] Wallet client handles error quote without exception.
- [ ] Wallet client parses successful quote correctly.
- [ ] Orchestration does not proceed to send after rejected quote.
- [ ] Rejected quote result is fail-closed.

---

# 5. P0 — Add Explicit Audit Event for Backend Balance Failure

## 5.1 Problem

If `backend.get_balance_sats()` fails during `capped_send()`, the service updates spend status but does not write a specific backend-failure audit event.

## 5.2 Required Behavior

When backend balance lookup fails:

- [ ] Catch the backend exception.
- [ ] Return structured failure response.
- [ ] Use reason code `backend_error` or `wallet_balance_failed`.
- [ ] Update spend request status appropriately.
- [ ] Write explicit audit event.
- [ ] Do not call fee quote.
- [ ] Do not call unlock.
- [ ] Do not call send.
- [ ] Do not record wallet transaction.
- [ ] Do not leak backend secrets/details.

## 5.3 Suggested Audit Event

Use one of:

```text
wallet_backend_balance_failed
wallet_backend_failure
```

Audit payload should include:

- [ ] spend_request_id
- [ ] idempotency_key
- [ ] reason code
- [ ] backend mode if safe
- [ ] sanitized request summary
- [ ] no secrets

## 5.4 Required Tests

- [ ] Backend balance failure returns structured failure.
- [ ] Backend balance failure updates spend status.
- [ ] Backend balance failure writes audit event.
- [ ] Backend balance failure does not call fee quote.
- [ ] Backend balance failure does not call unlock.
- [ ] Backend balance failure does not call send.
- [ ] Backend balance failure does not record wallet transaction.
- [ ] Backend balance failure response does not leak secrets.

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

- [ ] Wallet service checks evidence artifact type.
- [ ] Reject spend evidence with type not in allowlist.
- [ ] Rejection reason: `evidence_type_not_allowed`.
- [ ] Rejection writes audit event.
- [ ] Backend is not called after disallowed evidence type.
- [ ] Allowlist is configurable or centrally defined.
- [ ] Tests use both allowed and disallowed artifact types.

## 6.4 Required Tests

- [ ] `terms_snapshot` accepted as spend evidence.
- [ ] `receipt` accepted as spend evidence.
- [ ] `invoice` accepted as spend evidence.
- [ ] `payment_request` accepted as spend evidence.
- [ ] `random_note` rejected as spend evidence.
- [ ] `scratchpad` rejected as spend evidence.
- [ ] `debug_dump` rejected as spend evidence.
- [ ] Disallowed evidence type writes audit event.
- [ ] Disallowed evidence type does not call backend.

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

- [ ] Add `amount_sats` to wallet transaction record/model.
- [ ] Add `fee_sats` to wallet transaction record/model.
- [ ] Add migration if needed.
- [ ] Populate sat fields when recording wallet transactions.
- [ ] Validate consistency between BTC string and sat fields if both exist.
- [ ] Avoid using float for internal BTC accounting.
- [ ] Use integer sats in summary APIs.

## 7.4 Summary API Requirements

Update:

```text
get_experiment_spend_total(experiment_id)
get_spend_by_category(...)
```

They should:

- [ ] sum `amount_sats`
- [ ] sum `fee_sats`
- [ ] return total sats
- [ ] return fee sats
- [ ] optionally return display BTC string/Decimal
- [ ] return USD totals using decimal-safe values
- [ ] avoid SQL `CAST(amount_btc AS REAL)` for BTC aggregation
- [ ] count only actual spend statuses: `sent`, `confirmed`
- [ ] exclude non-spend statuses

## 7.5 Required Tests

- [ ] Recording transaction stores amount_sats.
- [ ] Recording transaction stores fee_sats.
- [ ] Summary total uses amount_sats.
- [ ] Summary fee total uses fee_sats.
- [ ] Tiny satoshi values aggregate exactly.
- [ ] Multiple transactions aggregate exactly.
- [ ] No floating-point rounding error in BTC summaries.
- [ ] Proposed/rejected/failed/cancelled spends excluded.
- [ ] Sent/confirmed spends included.
- [ ] Category summaries use integer sats.
- [ ] Existing tests still pass.

---

# 8. P2 — Add Code Review 3 Documentation

## 8.1 Required Files

Add:

- [ ] `docs/CODE_REVIEW3_SPEC.md`
- [ ] `docs/CODE_REVIEW3_TODO.md`
- [ ] `docs/CODE_REVIEW3_FIXES.md`, after implementation

## 8.2 `CODE_REVIEW3_FIXES.md`

After implementation, include:

- [ ] summary of fixed P0 issues
- [ ] summary of fixed P1 issues
- [ ] changed files
- [ ] test command
- [ ] test result summary
- [ ] deferred work
- [ ] safety notes
- [ ] confirmation that real spend remains disabled by default
- [ ] confirmation that Bitcoin Core backend remains disabled by default

---

# 9. P2 — Add Focused Regression Test File

Create a focused regression test file, for example:

```text
tests/test_code_review3_regressions.py
```

It should include direct tests for:

- [ ] invalid BTC-looking quote destination rejected
- [ ] invalid BTC-looking send destination rejected
- [ ] network mismatch rejected
- [ ] blocklisted destination rejected
- [ ] rejected quote response does not crash client
- [ ] balance failure audit event
- [ ] disallowed evidence type rejected
- [ ] satoshi aggregation exactness

---

# 10. Final Acceptance Criteria

This TODO is complete when:

- [ ] BTC validation is checksum-aware.
- [ ] BTC validation rejects malformed Bitcoin-looking strings.
- [ ] BTC validation is network-aware.
- [ ] Quote path uses real BTC validation.
- [ ] Send path uses real BTC validation.
- [ ] Destination blocklist exists and is enforced in quote.
- [ ] Destination blocklist exists and is enforced in send.
- [ ] Wallet client handles rejected quote responses without exception.
- [ ] Backend balance failure writes explicit audit event.
- [ ] Wallet service rejects disallowed spend-evidence artifact types.
- [ ] Ledger BTC summary APIs use integer sats or otherwise avoid float BTC aggregation.
- [ ] New regression tests cover every item above.
- [ ] Full test suite passes.
- [ ] Real wallet spending remains disabled by default.
- [ ] Bitcoin Core backend remains disabled by default.
- [ ] No secrets are committed.
- [ ] No arbitrary Bitcoin RPC passthrough exists.

---

# 11. Final Instruction

Do not connect real BTC after this implementation pass until the resulting code has been reviewed again.
