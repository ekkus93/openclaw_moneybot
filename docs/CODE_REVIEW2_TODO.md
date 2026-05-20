# CODE_REVIEW2_TODO.md

# OpenClaw MoneyBot — Code Review 2 TODO

This TODO is based on the review of the latest Copilot implementation after `CODE_REVIEW1_TODO.md`.

The latest implementation passed tests, but several important issues remain before real BTC can be connected.

## Priority Legend

```text
P0 = must fix before any real wallet connection or real spend
P1 = must fix before serious autonomous operation
P2 = documentation / cleanup / hardening
```

---

# 0. Global Rules

- [x] Continue from the latest Copilot implementation reviewed after Code Review 1.
- [x] Keep real wallet spending disabled by default.
- [x] Keep Bitcoin Core backend disabled by default.
- [x] Keep email sending disabled by default.
- [x] Keep browser automation non-executing/disabled by default.
- [x] Do not add arbitrary Bitcoin RPC passthrough.
- [x] Do not add `sendall`, `dumpprivkey`, `dumpwallet`, or equivalent methods.
- [x] Do not commit wallet passphrases.
- [x] Do not commit private keys.
- [x] Do not commit Bitcoin Core RPC cookies.
- [x] Do not commit seed phrases.
- [x] Do not put secrets in tests, fixtures, logs, prompts, or docs.
- [x] Fail closed on malformed, missing, ambiguous, or unverifiable data.
- [x] Add regression tests for every fixed issue.
- [x] Run the full test suite before completion.

---

# 1. P0 — Persist Policy Action Metadata

## 1.1 Problem

The wallet-governor service currently verifies that a linked policy decision is `allow`, but it cannot prove that the policy decision approved the exact executable wallet action.

A research policy approval for the same opportunity could potentially be reused as spend authorization.

## 1.2 Required Design

Persist enough policy request/action metadata for the wallet service to verify what was approved.

## 1.3 Required Fields

Add these fields to persisted policy decision records, or add a linked policy request/action record:

- [x] `action_type`
- [x] `category`
- [x] `requires_payment`
- [x] `requires_wallet_action`
- [x] `amount_usd`
- [x] `counterparty`
- [x] `opportunity_id`
- [x] `experiment_id`
- [x] `spend_request_id`, if applicable
- [x] `planned_tools`
- [x] sanitized raw policy input
- [x] optional policy input hash

## 1.4 Schema / Model Work

- [x] Update Pydantic policy models.
- [x] Update SQLite schema/migration.
- [x] Update ledger insert method for policy decisions.
- [x] Update ledger read method for policy decisions.
- [x] Update raw JSON serialization.
- [x] Update tests/fixtures that create policy decisions.
- [x] Preserve backward compatibility only if required; otherwise update fixtures cleanly.

## 1.5 Wallet Service Validation

In wallet-governor service validation:

- [x] Reject if policy action metadata is missing.
- [x] Reject if `policy.decision != allow`.
- [x] Reject if `policy.action_type` is not one of:
  - [x] `SPEND`
  - [x] `WALLET_TRANSFER`
  - [x] `PURCHASE`
- [x] Reject if `policy.requires_wallet_action != true`.
- [x] Reject if `policy.requires_payment != true`.
- [x] Reject if policy `amount_usd` is missing.
- [x] Reject if spend request amount exceeds policy-approved amount.
- [x] Reject if policy counterparty conflicts with spend request counterparty.
- [x] Reject if policy category conflicts with spend request category.
- [x] Reject if policy opportunity ID conflicts with spend request opportunity ID.
- [x] Reject if policy experiment ID conflicts with spend request experiment ID, when applicable.
- [x] Reject if policy planned tools do not include wallet spend or wallet governor, if planned tools are enforced.

## 1.6 Required Tests

- [x] Wallet service accepts executable spend policy.
- [x] Wallet service accepts executable wallet-transfer policy.
- [x] Wallet service accepts executable purchase policy when all other gates pass.
- [x] Wallet service rejects research policy.
- [x] Wallet service rejects email-draft policy.
- [x] Wallet service rejects read-only/browser policy.
- [x] Wallet service rejects policy with missing action metadata.
- [x] Wallet service rejects policy with `requires_wallet_action=false`.
- [x] Wallet service rejects policy with `requires_payment=false`.
- [x] Wallet service rejects policy amount lower than spend request amount.
- [x] Wallet service rejects policy counterparty mismatch.
- [x] Wallet service rejects policy category mismatch.
- [x] Wallet service rejects policy opportunity mismatch.
- [x] Existing policy guard tests still pass.

---

# 2. P0 — Reject Request/Ledger Authorization Mismatches

## 2.1 Problem

The wallet-governor service uses ledger spend request IDs internally, which is good, but it does not reject incoming request fields that conflict with the ledger spend request.

Observed bad behavior:

```text
request.policy_decision_id = different ID  -> sent
request.budget_plan_id = different ID      -> sent
request.evidence_archive_ids = []          -> sent
```

## 2.2 Required Validation

In the wallet service, compare incoming request fields against the ledger spend request.

Reject mismatches for:

- [x] `policy_decision_id`
- [x] `budget_plan_id`
- [x] `evidence_archive_ids`
- [x] amount
- [x] destination
- [x] category
- [x] counterparty, when present
- [x] purpose, when materially inconsistent
- [x] opportunity ID, if request includes it
- [x] experiment ID, if request includes it

## 2.3 Evidence ID Comparison Rules

- [x] Treat evidence IDs as sets unless order is semantically required.
- [x] Reject if request omits required ledger evidence IDs.
- [x] Reject if request adds unrelated evidence IDs.
- [x] Reject if request evidence IDs do not exactly match the spend request evidence IDs, unless explicitly documented otherwise.

## 2.4 Rejection Reason

Use structured reason code:

```text
spend_request_mismatch
```

or more specific codes:

```text
policy_id_mismatch
budget_id_mismatch
evidence_ids_mismatch
amount_mismatch
destination_mismatch
category_mismatch
counterparty_mismatch
purpose_mismatch
```

## 2.5 Required Tests

- [x] Reject request policy ID mismatch.
- [x] Reject request budget ID mismatch.
- [x] Reject request evidence ID mismatch.
- [x] Reject request missing evidence ID.
- [x] Reject request added unrelated evidence ID.
- [x] Reject request amount mismatch.
- [x] Reject request destination mismatch.
- [x] Reject request category mismatch.
- [x] Reject request counterparty mismatch.
- [x] Accept matching request/ledger fields.
- [x] Rejection writes audit event.
- [x] Rejection updates spend request status where appropriate.
- [x] Wallet backend is not called on mismatch.

---

# 3. P0 — Update Spend Status on All Rejections

## 3.1 Problem

If `spend_enabled=false`, the service rejects early and leaves a valid prewritten spend request in `proposed`.

## 3.2 Required Flow

- [x] Parse request enough to get `spend_request_id`.
- [x] If `spend_request_id` exists, attempt to load the spend request before early rejection.
- [x] If request must be rejected and spend request is eligible, update status to `rejected`.
- [x] Preserve terminal statuses.
- [x] Record audit event.

## 3.3 Eligible Rejection Transitions

- [x] `proposed -> rejected`
- [x] `approved -> rejected`
- [x] `sending -> failed` for backend failures

## 3.4 Terminal Statuses

Do not mutate these during ordinary rejection:

- [x] `sent`
- [x] `confirmed`
- [x] `failed`
- [x] `rejected`
- [x] `cancelled`

## 3.5 Required Tests

- [x] `spend_disabled` rejection updates proposed spend to rejected.
- [x] `spend_disabled` rejection updates approved spend to rejected.
- [x] `spend_disabled` rejection does not mutate already sent spend.
- [x] validation rejection updates proposed spend to rejected.
- [x] validation rejection updates approved spend to rejected.
- [x] backend failure updates sending spend to failed.
- [x] all rejection status updates create audit events.
- [x] missing spend request ID still returns structured rejection.

---

# 4. P0 — Validate Destination in Quote Path

## 4.1 Problem

`/quote-spend` accepts malformed BTC destinations. Send path validates destination, but quote path must also validate it.

## 4.2 Required Validation

Apply the same destination validation to quote as send:

- [x] require destination
- [x] reject empty destination
- [x] reject placeholder/test strings
- [x] reject malformed BTC address
- [x] reject unsupported network address
- [x] reject configured destination blocklist hits
- [x] reject `send_all`
- [x] reject `sweep`
- [x] reject `max`
- [x] reject `all funds`
- [x] reject equivalent send-all language
- [x] do not unlock wallet for quote
- [x] do not call send backend for quote

## 4.3 Required Tests

- [x] Quote rejects `not-a-btc-address`.
- [x] Quote rejects empty destination.
- [x] Quote rejects placeholder destination.
- [x] Quote rejects send-all language.
- [x] Quote rejects unsupported network address.
- [x] Quote accepts valid configured-network BTC destination.
- [x] Quote does not call wallet unlock.
- [x] Quote does not call wallet send.

---

# 5. P0 — Durable Quote/Unlock/Backend Failure Handling

## 5.1 Problem

Backend failures from quote, fee estimation, wallet unlock, wallet send, or wallet lock may not always become structured durable rejection/failure records.

## 5.2 Quote/Fee Failure Handling

- [x] Wrap fee estimation failures.
- [x] Return structured failure response.
- [x] Use reason code `fee_quote_failed`.
- [x] Record audit event.
- [x] Update spend request status to `rejected` when appropriate.
- [x] Do not call wallet unlock.
- [x] Do not call wallet send.

## 5.3 Unlock Failure Handling

- [x] Wrap wallet unlock failures.
- [x] Return structured failure response.
- [x] Use reason code `backend_error` or `wallet_unlock_failed`.
- [x] Record audit event.
- [x] Update spend request status to `failed` or `rejected`, depending on state.
- [x] Do not call wallet send if unlock fails.
- [x] Attempt wallet lock in a best-effort safe block if unlock state is ambiguous.
- [x] Do not leak passphrase or backend details.

## 5.4 Send Failure Handling

- [x] Wrap wallet send failures.
- [x] Return structured failure response.
- [x] Use reason code `backend_error` or `wallet_send_failed`.
- [x] Record audit event.
- [x] Update spend request status to `failed`.
- [x] Attempt wallet lock in `finally`.
- [x] Do not record successful wallet transaction.

## 5.5 Lock Failure Handling

- [x] Catch wallet lock failures in `finally`.
- [x] Record audit event with reason code `wallet_lock_failed`.
- [x] Do not mark spend as successful solely because lock failed.
- [x] If send succeeded but lock failed, return success with warning or failure requiring review; choose one and document it.
- [x] Never leak secrets in lock failure logs.

## 5.6 Required Tests

- [x] Fee quote failure returns structured rejection.
- [x] Fee quote failure writes audit event.
- [x] Fee quote failure updates spend request status.
- [x] Unlock failure returns structured failure.
- [x] Unlock failure writes audit event.
- [x] Unlock failure does not call send.
- [x] Send failure returns structured failure.
- [x] Send failure writes audit event.
- [x] Send failure updates status to failed.
- [x] Send failure does not record wallet transaction.
- [x] Lock failure writes audit event.
- [x] Lock failure does not leak secrets.
- [x] Backend exception does not crash HTTP route with traceback.

---

# 6. P1 — Fix Budget Planner Decision Precedence

## 6.1 Problem

Budget planner can downgrade hard rejection into `simulate`.

Example:

```text
policy = block
tos = missing
expected_revenue_unknown = true
actual final decision = simulate
```

This is wrong. Hard blockers must dominate.

## 6.2 Required Decision Precedence

Implement final decision precedence:

```text
REJECT > HUMAN_REVIEW > SIMULATE > EXECUTE_REQUEST
```

## 6.3 Hard Reject Conditions

Final decision must be `reject` when:

- [x] policy decision is not exactly `allow`
- [x] TOS/legal decision is not exactly `proceed`
- [x] spend exceeds max loss
- [x] spend exceeds configured budget
- [x] spend amount is negative
- [x] max loss is negative
- [x] prohibited category is present
- [x] wallet spend is requested but not allowed
- [x] required references are missing
- [x] recurring cost is uncapped if policy treats this as reject

## 6.4 Human Review Conditions

Final decision should be `human_review` when:

- [x] terms are unclear but not hard-rejected
- [x] identity/KYC requirements are unclear
- [x] recurring billing exists and requires human choice
- [x] legal/TOS ambiguity remains
- [x] high uncertainty requires human operator

## 6.5 Simulate Conditions

Final decision may be `simulate` only when:

- [x] no hard reject exists
- [x] no human review blocker exists
- [x] expected revenue is unknown
- [x] expected ROI is uncertain
- [x] dry-run is recommended before spend

## 6.6 Required Tests

- [x] Policy block plus revenue uncertainty returns reject.
- [x] TOS reject plus revenue uncertainty returns reject.
- [x] Missing policy returns reject or human_review, not simulate.
- [x] Missing TOS returns reject or human_review, not simulate.
- [x] Revenue uncertainty alone returns simulate.
- [x] Human-review blocker beats simulate.
- [x] Reject beats human_review.
- [x] Valid low-risk plan returns execute.

---

# 7. P1 — Gracefully Handle Missing Budget References

## 7.1 Problem

The budget planner can crash with SQLite FK errors if given nonexistent policy/TOS IDs.

## 7.2 Required Fix

Before inserting budget plan:

- [x] Load referenced policy decision.
- [x] Load referenced TOS/legal check.
- [x] Load referenced opportunity, if applicable.
- [x] If required reference is missing, return structured reject/human-review result.
- [x] Do not attempt invalid ledger insert.
- [x] Record audit event or validation failure if applicable.
- [x] Return useful reason codes.

## 7.3 Suggested Reason Codes

```text
policy_missing
tos_missing
opportunity_missing
invalid_reference
```

## 7.4 Required Tests

- [x] Nonexistent policy ID does not raise SQLite FK error.
- [x] Nonexistent TOS ID does not raise SQLite FK error.
- [x] Nonexistent opportunity ID does not raise SQLite FK error.
- [x] Missing policy produces structured reject/human_review.
- [x] Missing TOS produces structured reject/human_review.
- [x] Valid references still insert budget plan.
- [x] Validation failure is auditable or visible in returned reasons.

---

# 8. P1 — Enforce Evidence `content_text` Size Limit

## 8.1 Problem

File input is size-limited, but direct `content_text` input can exceed `max_artifact_bytes`.

## 8.2 Required Fix

- [x] Convert `content_text` to bytes.
- [x] Check byte length.
- [x] Reject if byte length exceeds `max_artifact_bytes`.
- [x] Return clear error.
- [x] Do not write file.
- [x] Do not write ledger artifact record.

## 8.3 Required Tests

- [x] Oversized `content_text` rejected.
- [x] Boundary-size `content_text` accepted.
- [x] Small `content_text` accepted.
- [x] Rejected text does not create archive file.
- [x] Rejected text does not create ledger artifact.

---

# 9. P1 — Strictly Sanitize Evidence Type

## 9.1 Problem

`evidence_type` normalization is too weak and can produce unsafe path components or runtime errors.

## 9.2 Required Validation

After normalization, require:

```regex
^[a-z0-9_]{1,64}$
```

Reject evidence types containing:

- [x] `/`
- [x] `\`
- [x] `..`
- [x] null byte
- [x] whitespace after normalization, if not expected
- [x] shell metacharacters
- [x] path separators
- [x] empty string
- [x] strings longer than 64 chars

## 9.3 Required Tests

- [x] Reject `../../evil`.
- [x] Reject `foo/bar`.
- [x] Reject `foo\bar`.
- [x] Reject null-byte evidence type.
- [x] Reject empty evidence type.
- [x] Reject overlong evidence type.
- [x] Accept `receipt`.
- [x] Accept `terms_snapshot`.
- [x] Accept `wallet_transaction`.
- [x] Reject unsafe type without creating file or ledger record.

---

# 10. P1 — Verify Evidence Path and Hash in Wallet Service

## 10.1 Problem

Wallet service verifies evidence ledger IDs, but not necessarily that archived files exist and hashes match.

## 10.2 Required Evidence Validation Helper

Implement a helper such as:

```text
validate_evidence_artifact(evidence_id, expected_context) -> EvidenceValidationResult
```

It should verify:

- [x] ledger evidence record exists
- [x] archive path is present
- [x] archive path resolves under configured archive root
- [x] archive file exists
- [x] archive path is regular file
- [x] archive hash exists
- [x] archive file hash matches ledger hash
- [x] metadata file exists if required
- [x] related record type/id is compatible with spend authorization context
- [x] artifact type is acceptable for spend evidence

## 10.3 Wallet Service Integration

- [x] Call evidence validation for every required evidence ID before send.
- [x] Reject spend if any evidence file is missing.
- [x] Reject spend if any evidence hash mismatches.
- [x] Reject spend if evidence path escapes archive root.
- [x] Reject spend if evidence is unrelated to the spend/opportunity/experiment/budget.
- [x] Record reason code:
  - [x] `evidence_missing`
  - [x] `evidence_hash_mismatch`
  - [x] `evidence_path_invalid`
  - [x] `evidence_unrelated`

## 10.4 Required Tests

- [x] Missing evidence file rejects spend.
- [x] Evidence hash mismatch rejects spend.
- [x] Evidence path outside archive root rejects spend.
- [x] Evidence unrelated to spend rejects spend.
- [x] Valid evidence file/hash/context allows spend.
- [x] Evidence validation rejection writes audit event.
- [x] Wallet backend not called on evidence validation failure.

---

# 11. P1 — Add Explicit Ledger Spend Summary APIs

## 11.1 Required APIs

Add methods such as:

```text
get_experiment_spend_total(experiment_id)
get_spend_by_category(...)
```

## 11.2 `get_experiment_spend_total`

Should:

- [x] Accept `experiment_id`.
- [x] Count only actual spend statuses.
- [x] Include `sent`.
- [x] Include `confirmed`.
- [x] Exclude `proposed`.
- [x] Exclude `approved`.
- [x] Exclude `rejected`.
- [x] Exclude `failed`.
- [x] Exclude `cancelled`.
- [x] Include fees if configured or return separate amount/fee fields.
- [x] Return USD amount.
- [x] Return BTC amount if applicable.
- [x] Return fee totals if available.

## 11.3 `get_spend_by_category`

Should support:

- [x] optional date range
- [x] optional experiment ID
- [x] optional opportunity ID
- [x] only actual spend statuses
- [x] category totals in USD
- [x] category totals in BTC if applicable
- [x] fee totals if available

## 11.4 Required Tests

- [x] Experiment spend total includes sent spend.
- [x] Experiment spend total includes confirmed spend.
- [x] Experiment spend total excludes proposed spend.
- [x] Experiment spend total excludes rejected spend.
- [x] Experiment spend total excludes failed spend.
- [x] Experiment spend total includes fees correctly.
- [x] Spend by category groups correctly.
- [x] Spend by category respects date range.
- [x] Spend by category respects experiment filter.
- [x] Spend by category excludes non-spend records.

---

# 12. P2 — Remove or Correct Stale Work-Split Documentation

## 12.1 Problem

Repo docs still contain stale instructions suggesting splitting work between Copilot and OpenCode.

The desired process is:

```text
Both Copilot and OpenCode independently implement the same TODO from the same starting codebase.
```

## 12.2 Required Work

- [x] Search docs for “Suggested Work Split”.
- [x] Search docs for “Copilot should focus”.
- [x] Search docs for “OpenCode should focus”.
- [x] Search docs for module-specific agent assignments.
- [x] Remove stale work-split text.
- [x] Replace with parallel implementation comparison instructions if the file is kept.
- [x] Ensure README does not instruct split work.
- [x] Ensure `CODE_REVIEW1_TODO.md` copy in repo is corrected or removed.

## 12.3 Required Tests / Checks

- [x] Add docs check or simple grep-based test if practical.
- [x] Confirm no stale split-work phrase remains.
- [x] Confirm docs say both agents independently implement the same TODO.

---

# 13. P2 — Add Code Review 2 Documentation

## 13.1 Required Files

Add:

- [x] `docs/CODE_REVIEW2_SPEC.md`
- [x] `docs/CODE_REVIEW2_TODO.md`
- [x] `docs/CODE_REVIEW2_FIXES.md`, after implementation

## 13.2 `CODE_REVIEW2_FIXES.md`

After implementation, include:

- [x] summary of fixed P0 issues
- [x] summary of fixed P1 issues
- [x] changed files
- [x] test command
- [x] test result summary
- [x] deferred work
- [x] safety notes
- [x] confirmation that real spend remains disabled by default

---

# 14. Final Acceptance Criteria

This TODO is complete when:

- [x] Policy action metadata is persisted and read back.
- [x] Wallet service rejects non-executable policy approvals.
- [x] Wallet service rejects research/email/browser policy approvals for spend.
- [x] Wallet service rejects request/ledger policy ID mismatch.
- [x] Wallet service rejects request/ledger budget ID mismatch.
- [x] Wallet service rejects request/ledger evidence ID mismatch.
- [x] Spend-disabled rejection updates eligible spend requests to rejected.
- [x] Quote rejects malformed BTC destinations.
- [x] Fee quote failure creates structured durable rejection.
- [x] Unlock failure creates structured durable failure.
- [x] Send failure creates structured durable failure.
- [x] Lock failure records audit event.
- [x] Budget hard rejections cannot become simulate.
- [x] Budget missing references do not crash with SQLite FK errors.
- [x] Oversized `content_text` evidence is rejected.
- [x] Unsafe `evidence_type` is rejected.
- [x] Wallet service verifies evidence file path and hash.
- [x] Ledger exposes explicit experiment spend total API.
- [x] Ledger exposes explicit spend-by-category API.
- [x] Stale split-work docs are removed or corrected.
- [x] Full test suite passes.
- [x] Real wallet spending remains disabled by default.
- [x] Bitcoin Core backend remains disabled by default.
- [x] No secrets are committed.
- [x] No arbitrary Bitcoin RPC passthrough exists.

---

# 15. Final Instruction

Do not connect real BTC after this implementation pass until the resulting code has been reviewed again.
