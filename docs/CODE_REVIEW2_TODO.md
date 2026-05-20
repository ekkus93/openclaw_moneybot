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

- [ ] Continue from the latest Copilot implementation reviewed after Code Review 1.
- [ ] Keep real wallet spending disabled by default.
- [ ] Keep Bitcoin Core backend disabled by default.
- [ ] Keep email sending disabled by default.
- [ ] Keep browser automation non-executing/disabled by default.
- [ ] Do not add arbitrary Bitcoin RPC passthrough.
- [ ] Do not add `sendall`, `dumpprivkey`, `dumpwallet`, or equivalent methods.
- [ ] Do not commit wallet passphrases.
- [ ] Do not commit private keys.
- [ ] Do not commit Bitcoin Core RPC cookies.
- [ ] Do not commit seed phrases.
- [ ] Do not put secrets in tests, fixtures, logs, prompts, or docs.
- [ ] Fail closed on malformed, missing, ambiguous, or unverifiable data.
- [ ] Add regression tests for every fixed issue.
- [ ] Run the full test suite before completion.

---

# 1. P0 — Persist Policy Action Metadata

## 1.1 Problem

The wallet-governor service currently verifies that a linked policy decision is `allow`, but it cannot prove that the policy decision approved the exact executable wallet action.

A research policy approval for the same opportunity could potentially be reused as spend authorization.

## 1.2 Required Design

Persist enough policy request/action metadata for the wallet service to verify what was approved.

## 1.3 Required Fields

Add these fields to persisted policy decision records, or add a linked policy request/action record:

- [ ] `action_type`
- [ ] `category`
- [ ] `requires_payment`
- [ ] `requires_wallet_action`
- [ ] `amount_usd`
- [ ] `counterparty`
- [ ] `opportunity_id`
- [ ] `experiment_id`
- [ ] `spend_request_id`, if applicable
- [ ] `planned_tools`
- [ ] sanitized raw policy input
- [ ] optional policy input hash

## 1.4 Schema / Model Work

- [ ] Update Pydantic policy models.
- [ ] Update SQLite schema/migration.
- [ ] Update ledger insert method for policy decisions.
- [ ] Update ledger read method for policy decisions.
- [ ] Update raw JSON serialization.
- [ ] Update tests/fixtures that create policy decisions.
- [ ] Preserve backward compatibility only if required; otherwise update fixtures cleanly.

## 1.5 Wallet Service Validation

In wallet-governor service validation:

- [ ] Reject if policy action metadata is missing.
- [ ] Reject if `policy.decision != allow`.
- [ ] Reject if `policy.action_type` is not one of:
  - [ ] `SPEND`
  - [ ] `WALLET_TRANSFER`
  - [ ] `PURCHASE`
- [ ] Reject if `policy.requires_wallet_action != true`.
- [ ] Reject if `policy.requires_payment != true`.
- [ ] Reject if policy `amount_usd` is missing.
- [ ] Reject if spend request amount exceeds policy-approved amount.
- [ ] Reject if policy counterparty conflicts with spend request counterparty.
- [ ] Reject if policy category conflicts with spend request category.
- [ ] Reject if policy opportunity ID conflicts with spend request opportunity ID.
- [ ] Reject if policy experiment ID conflicts with spend request experiment ID, when applicable.
- [ ] Reject if policy planned tools do not include wallet spend or wallet governor, if planned tools are enforced.

## 1.6 Required Tests

- [ ] Wallet service accepts executable spend policy.
- [ ] Wallet service accepts executable wallet-transfer policy.
- [ ] Wallet service accepts executable purchase policy when all other gates pass.
- [ ] Wallet service rejects research policy.
- [ ] Wallet service rejects email-draft policy.
- [ ] Wallet service rejects read-only/browser policy.
- [ ] Wallet service rejects policy with missing action metadata.
- [ ] Wallet service rejects policy with `requires_wallet_action=false`.
- [ ] Wallet service rejects policy with `requires_payment=false`.
- [ ] Wallet service rejects policy amount lower than spend request amount.
- [ ] Wallet service rejects policy counterparty mismatch.
- [ ] Wallet service rejects policy category mismatch.
- [ ] Wallet service rejects policy opportunity mismatch.
- [ ] Existing policy guard tests still pass.

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

- [ ] `policy_decision_id`
- [ ] `budget_plan_id`
- [ ] `evidence_archive_ids`
- [ ] amount
- [ ] destination
- [ ] category
- [ ] counterparty, when present
- [ ] purpose, when materially inconsistent
- [ ] opportunity ID, if request includes it
- [ ] experiment ID, if request includes it

## 2.3 Evidence ID Comparison Rules

- [ ] Treat evidence IDs as sets unless order is semantically required.
- [ ] Reject if request omits required ledger evidence IDs.
- [ ] Reject if request adds unrelated evidence IDs.
- [ ] Reject if request evidence IDs do not exactly match the spend request evidence IDs, unless explicitly documented otherwise.

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

- [ ] Reject request policy ID mismatch.
- [ ] Reject request budget ID mismatch.
- [ ] Reject request evidence ID mismatch.
- [ ] Reject request missing evidence ID.
- [ ] Reject request added unrelated evidence ID.
- [ ] Reject request amount mismatch.
- [ ] Reject request destination mismatch.
- [ ] Reject request category mismatch.
- [ ] Reject request counterparty mismatch.
- [ ] Accept matching request/ledger fields.
- [ ] Rejection writes audit event.
- [ ] Rejection updates spend request status where appropriate.
- [ ] Wallet backend is not called on mismatch.

---

# 3. P0 — Update Spend Status on All Rejections

## 3.1 Problem

If `spend_enabled=false`, the service rejects early and leaves a valid prewritten spend request in `proposed`.

## 3.2 Required Flow

- [ ] Parse request enough to get `spend_request_id`.
- [ ] If `spend_request_id` exists, attempt to load the spend request before early rejection.
- [ ] If request must be rejected and spend request is eligible, update status to `rejected`.
- [ ] Preserve terminal statuses.
- [ ] Record audit event.

## 3.3 Eligible Rejection Transitions

- [ ] `proposed -> rejected`
- [ ] `approved -> rejected`
- [ ] `sending -> failed` for backend failures

## 3.4 Terminal Statuses

Do not mutate these during ordinary rejection:

- [ ] `sent`
- [ ] `confirmed`
- [ ] `failed`
- [ ] `rejected`
- [ ] `cancelled`

## 3.5 Required Tests

- [ ] `spend_disabled` rejection updates proposed spend to rejected.
- [ ] `spend_disabled` rejection updates approved spend to rejected.
- [ ] `spend_disabled` rejection does not mutate already sent spend.
- [ ] validation rejection updates proposed spend to rejected.
- [ ] validation rejection updates approved spend to rejected.
- [ ] backend failure updates sending spend to failed.
- [ ] all rejection status updates create audit events.
- [ ] missing spend request ID still returns structured rejection.

---

# 4. P0 — Validate Destination in Quote Path

## 4.1 Problem

`/quote-spend` accepts malformed BTC destinations. Send path validates destination, but quote path must also validate it.

## 4.2 Required Validation

Apply the same destination validation to quote as send:

- [ ] require destination
- [ ] reject empty destination
- [ ] reject placeholder/test strings
- [ ] reject malformed BTC address
- [ ] reject unsupported network address
- [ ] reject configured destination blocklist hits
- [ ] reject `send_all`
- [ ] reject `sweep`
- [ ] reject `max`
- [ ] reject `all funds`
- [ ] reject equivalent send-all language
- [ ] do not unlock wallet for quote
- [ ] do not call send backend for quote

## 4.3 Required Tests

- [ ] Quote rejects `not-a-btc-address`.
- [ ] Quote rejects empty destination.
- [ ] Quote rejects placeholder destination.
- [ ] Quote rejects send-all language.
- [ ] Quote rejects unsupported network address.
- [ ] Quote accepts valid configured-network BTC destination.
- [ ] Quote does not call wallet unlock.
- [ ] Quote does not call wallet send.

---

# 5. P0 — Durable Quote/Unlock/Backend Failure Handling

## 5.1 Problem

Backend failures from quote, fee estimation, wallet unlock, wallet send, or wallet lock may not always become structured durable rejection/failure records.

## 5.2 Quote/Fee Failure Handling

- [ ] Wrap fee estimation failures.
- [ ] Return structured failure response.
- [ ] Use reason code `fee_quote_failed`.
- [ ] Record audit event.
- [ ] Update spend request status to `rejected` when appropriate.
- [ ] Do not call wallet unlock.
- [ ] Do not call wallet send.

## 5.3 Unlock Failure Handling

- [ ] Wrap wallet unlock failures.
- [ ] Return structured failure response.
- [ ] Use reason code `backend_error` or `wallet_unlock_failed`.
- [ ] Record audit event.
- [ ] Update spend request status to `failed` or `rejected`, depending on state.
- [ ] Do not call wallet send if unlock fails.
- [ ] Attempt wallet lock in a best-effort safe block if unlock state is ambiguous.
- [ ] Do not leak passphrase or backend details.

## 5.4 Send Failure Handling

- [ ] Wrap wallet send failures.
- [ ] Return structured failure response.
- [ ] Use reason code `backend_error` or `wallet_send_failed`.
- [ ] Record audit event.
- [ ] Update spend request status to `failed`.
- [ ] Attempt wallet lock in `finally`.
- [ ] Do not record successful wallet transaction.

## 5.5 Lock Failure Handling

- [ ] Catch wallet lock failures in `finally`.
- [ ] Record audit event with reason code `wallet_lock_failed`.
- [ ] Do not mark spend as successful solely because lock failed.
- [ ] If send succeeded but lock failed, return success with warning or failure requiring review; choose one and document it.
- [ ] Never leak secrets in lock failure logs.

## 5.6 Required Tests

- [ ] Fee quote failure returns structured rejection.
- [ ] Fee quote failure writes audit event.
- [ ] Fee quote failure updates spend request status.
- [ ] Unlock failure returns structured failure.
- [ ] Unlock failure writes audit event.
- [ ] Unlock failure does not call send.
- [ ] Send failure returns structured failure.
- [ ] Send failure writes audit event.
- [ ] Send failure updates status to failed.
- [ ] Send failure does not record wallet transaction.
- [ ] Lock failure writes audit event.
- [ ] Lock failure does not leak secrets.
- [ ] Backend exception does not crash HTTP route with traceback.

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

- [ ] policy decision is not exactly `allow`
- [ ] TOS/legal decision is not exactly `proceed`
- [ ] spend exceeds max loss
- [ ] spend exceeds configured budget
- [ ] spend amount is negative
- [ ] max loss is negative
- [ ] prohibited category is present
- [ ] wallet spend is requested but not allowed
- [ ] required references are missing
- [ ] recurring cost is uncapped if policy treats this as reject

## 6.4 Human Review Conditions

Final decision should be `human_review` when:

- [ ] terms are unclear but not hard-rejected
- [ ] identity/KYC requirements are unclear
- [ ] recurring billing exists and requires human choice
- [ ] legal/TOS ambiguity remains
- [ ] high uncertainty requires human operator

## 6.5 Simulate Conditions

Final decision may be `simulate` only when:

- [ ] no hard reject exists
- [ ] no human review blocker exists
- [ ] expected revenue is unknown
- [ ] expected ROI is uncertain
- [ ] dry-run is recommended before spend

## 6.6 Required Tests

- [ ] Policy block plus revenue uncertainty returns reject.
- [ ] TOS reject plus revenue uncertainty returns reject.
- [ ] Missing policy returns reject or human_review, not simulate.
- [ ] Missing TOS returns reject or human_review, not simulate.
- [ ] Revenue uncertainty alone returns simulate.
- [ ] Human-review blocker beats simulate.
- [ ] Reject beats human_review.
- [ ] Valid low-risk plan returns execute.

---

# 7. P1 — Gracefully Handle Missing Budget References

## 7.1 Problem

The budget planner can crash with SQLite FK errors if given nonexistent policy/TOS IDs.

## 7.2 Required Fix

Before inserting budget plan:

- [ ] Load referenced policy decision.
- [ ] Load referenced TOS/legal check.
- [ ] Load referenced opportunity, if applicable.
- [ ] If required reference is missing, return structured reject/human-review result.
- [ ] Do not attempt invalid ledger insert.
- [ ] Record audit event or validation failure if applicable.
- [ ] Return useful reason codes.

## 7.3 Suggested Reason Codes

```text
policy_missing
tos_missing
opportunity_missing
invalid_reference
```

## 7.4 Required Tests

- [ ] Nonexistent policy ID does not raise SQLite FK error.
- [ ] Nonexistent TOS ID does not raise SQLite FK error.
- [ ] Nonexistent opportunity ID does not raise SQLite FK error.
- [ ] Missing policy produces structured reject/human_review.
- [ ] Missing TOS produces structured reject/human_review.
- [ ] Valid references still insert budget plan.
- [ ] Validation failure is auditable or visible in returned reasons.

---

# 8. P1 — Enforce Evidence `content_text` Size Limit

## 8.1 Problem

File input is size-limited, but direct `content_text` input can exceed `max_artifact_bytes`.

## 8.2 Required Fix

- [ ] Convert `content_text` to bytes.
- [ ] Check byte length.
- [ ] Reject if byte length exceeds `max_artifact_bytes`.
- [ ] Return clear error.
- [ ] Do not write file.
- [ ] Do not write ledger artifact record.

## 8.3 Required Tests

- [ ] Oversized `content_text` rejected.
- [ ] Boundary-size `content_text` accepted.
- [ ] Small `content_text` accepted.
- [ ] Rejected text does not create archive file.
- [ ] Rejected text does not create ledger artifact.

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

- [ ] `/`
- [ ] `\`
- [ ] `..`
- [ ] null byte
- [ ] whitespace after normalization, if not expected
- [ ] shell metacharacters
- [ ] path separators
- [ ] empty string
- [ ] strings longer than 64 chars

## 9.3 Required Tests

- [ ] Reject `../../evil`.
- [ ] Reject `foo/bar`.
- [ ] Reject `foo\bar`.
- [ ] Reject null-byte evidence type.
- [ ] Reject empty evidence type.
- [ ] Reject overlong evidence type.
- [ ] Accept `receipt`.
- [ ] Accept `terms_snapshot`.
- [ ] Accept `wallet_transaction`.
- [ ] Reject unsafe type without creating file or ledger record.

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

- [ ] ledger evidence record exists
- [ ] archive path is present
- [ ] archive path resolves under configured archive root
- [ ] archive file exists
- [ ] archive path is regular file
- [ ] archive hash exists
- [ ] archive file hash matches ledger hash
- [ ] metadata file exists if required
- [ ] related record type/id is compatible with spend authorization context
- [ ] artifact type is acceptable for spend evidence

## 10.3 Wallet Service Integration

- [ ] Call evidence validation for every required evidence ID before send.
- [ ] Reject spend if any evidence file is missing.
- [ ] Reject spend if any evidence hash mismatches.
- [ ] Reject spend if evidence path escapes archive root.
- [ ] Reject spend if evidence is unrelated to the spend/opportunity/experiment/budget.
- [ ] Record reason code:
  - [ ] `evidence_missing`
  - [ ] `evidence_hash_mismatch`
  - [ ] `evidence_path_invalid`
  - [ ] `evidence_unrelated`

## 10.4 Required Tests

- [ ] Missing evidence file rejects spend.
- [ ] Evidence hash mismatch rejects spend.
- [ ] Evidence path outside archive root rejects spend.
- [ ] Evidence unrelated to spend rejects spend.
- [ ] Valid evidence file/hash/context allows spend.
- [ ] Evidence validation rejection writes audit event.
- [ ] Wallet backend not called on evidence validation failure.

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

- [ ] Accept `experiment_id`.
- [ ] Count only actual spend statuses.
- [ ] Include `sent`.
- [ ] Include `confirmed`.
- [ ] Exclude `proposed`.
- [ ] Exclude `approved`.
- [ ] Exclude `rejected`.
- [ ] Exclude `failed`.
- [ ] Exclude `cancelled`.
- [ ] Include fees if configured or return separate amount/fee fields.
- [ ] Return USD amount.
- [ ] Return BTC amount if applicable.
- [ ] Return fee totals if available.

## 11.3 `get_spend_by_category`

Should support:

- [ ] optional date range
- [ ] optional experiment ID
- [ ] optional opportunity ID
- [ ] only actual spend statuses
- [ ] category totals in USD
- [ ] category totals in BTC if applicable
- [ ] fee totals if available

## 11.4 Required Tests

- [ ] Experiment spend total includes sent spend.
- [ ] Experiment spend total includes confirmed spend.
- [ ] Experiment spend total excludes proposed spend.
- [ ] Experiment spend total excludes rejected spend.
- [ ] Experiment spend total excludes failed spend.
- [ ] Experiment spend total includes fees correctly.
- [ ] Spend by category groups correctly.
- [ ] Spend by category respects date range.
- [ ] Spend by category respects experiment filter.
- [ ] Spend by category excludes non-spend records.

---

# 12. P2 — Remove or Correct Stale Work-Split Documentation

## 12.1 Problem

Repo docs still contain stale instructions suggesting splitting work between Copilot and OpenCode.

The desired process is:

```text
Both Copilot and OpenCode independently implement the same TODO from the same starting codebase.
```

## 12.2 Required Work

- [ ] Search docs for “Suggested Work Split”.
- [ ] Search docs for “Copilot should focus”.
- [ ] Search docs for “OpenCode should focus”.
- [ ] Search docs for module-specific agent assignments.
- [ ] Remove stale work-split text.
- [ ] Replace with parallel implementation comparison instructions if the file is kept.
- [ ] Ensure README does not instruct split work.
- [ ] Ensure `CODE_REVIEW1_TODO.md` copy in repo is corrected or removed.

## 12.3 Required Tests / Checks

- [ ] Add docs check or simple grep-based test if practical.
- [ ] Confirm no stale split-work phrase remains.
- [ ] Confirm docs say both agents independently implement the same TODO.

---

# 13. P2 — Add Code Review 2 Documentation

## 13.1 Required Files

Add:

- [ ] `docs/CODE_REVIEW2_SPEC.md`
- [ ] `docs/CODE_REVIEW2_TODO.md`
- [ ] `docs/CODE_REVIEW2_FIXES.md`, after implementation

## 13.2 `CODE_REVIEW2_FIXES.md`

After implementation, include:

- [ ] summary of fixed P0 issues
- [ ] summary of fixed P1 issues
- [ ] changed files
- [ ] test command
- [ ] test result summary
- [ ] deferred work
- [ ] safety notes
- [ ] confirmation that real spend remains disabled by default

---

# 14. Final Acceptance Criteria

This TODO is complete when:

- [ ] Policy action metadata is persisted and read back.
- [ ] Wallet service rejects non-executable policy approvals.
- [ ] Wallet service rejects research/email/browser policy approvals for spend.
- [ ] Wallet service rejects request/ledger policy ID mismatch.
- [ ] Wallet service rejects request/ledger budget ID mismatch.
- [ ] Wallet service rejects request/ledger evidence ID mismatch.
- [ ] Spend-disabled rejection updates eligible spend requests to rejected.
- [ ] Quote rejects malformed BTC destinations.
- [ ] Fee quote failure creates structured durable rejection.
- [ ] Unlock failure creates structured durable failure.
- [ ] Send failure creates structured durable failure.
- [ ] Lock failure records audit event.
- [ ] Budget hard rejections cannot become simulate.
- [ ] Budget missing references do not crash with SQLite FK errors.
- [ ] Oversized `content_text` evidence is rejected.
- [ ] Unsafe `evidence_type` is rejected.
- [ ] Wallet service verifies evidence file path and hash.
- [ ] Ledger exposes explicit experiment spend total API.
- [ ] Ledger exposes explicit spend-by-category API.
- [ ] Stale split-work docs are removed or corrected.
- [ ] Full test suite passes.
- [ ] Real wallet spending remains disabled by default.
- [ ] Bitcoin Core backend remains disabled by default.
- [ ] No secrets are committed.
- [ ] No arbitrary Bitcoin RPC passthrough exists.

---

# 15. Final Instruction

Do not connect real BTC after this implementation pass until the resulting code has been reviewed again.
