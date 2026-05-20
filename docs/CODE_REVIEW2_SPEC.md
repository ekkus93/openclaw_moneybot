# CODE_REVIEW2_SPEC.md

# OpenClaw MoneyBot — Code Review 2 Remediation Specification

## 1. Purpose

This specification defines the next remediation pass for the latest Copilot implementation of `openclaw_moneybot`.

The previous implementation pass made major progress:

- Wallet-governor service-side validation was added.
- Wallet client no longer accepts TOS/legal `human_review` for spend.
- Weekly spend SQL was fixed.
- Wallet HTTP service was added.
- Bitcoin Core backend skeleton was added and disabled by default.
- Evidence archiver received workspace/file safety checks.
- Policy guard, TOS/legal checker, budget planner, and test coverage were expanded.
- The full test suite passed in review: `272 passed`.

However, the latest review found several remaining issues that must be fixed before connecting real BTC, even for a small hot wallet.

This spec focuses only on the remaining gaps.

## 2. Current Readiness

Current status after the latest review:

```text
Dry-run readiness: good
Mock-wallet readiness: good
Real hot-wallet readiness: not yet
```

The next implementation pass must preserve all existing safety defaults:

- Real wallet spending disabled by default.
- Bitcoin Core backend disabled by default.
- Email sending disabled by default.
- Browser automation disabled/non-executing by default.
- No arbitrary Bitcoin RPC passthrough.
- No secrets in repo, tests, fixtures, prompts, logs, or docs.

## 3. Primary Goal

The primary goal is to make the wallet-governor service and adjacent authorization pipeline **unambiguously fail-closed**.

The wallet-governor service must be able to prove, using ledger records and validated metadata, that every wallet spend was approved for the exact executable action being requested.

It is not sufficient that the wallet client performed preflight checks. The service itself must verify the complete authorization chain.

## 4. Main Remaining Defects

The latest review identified these main defects:

```text
P0:
- Wallet service cannot prove policy approval was for the exact executable wallet action.
- Wallet service accepts request/ledger mismatches for policy ID, budget ID, and evidence IDs.
- spend_disabled rejection leaves existing spend request as proposed.
- /quote-spend accepts malformed BTC destinations.
- quote/unlock/backend failures are not durable structured rejections.

P1:
- Budget planner can downgrade hard rejection into simulate.
- Nonexistent policy/TOS IDs can cause SQLite FK crash.
- Evidence content_text max size is not enforced.
- evidence_type filename/path sanitization is too weak.
- Wallet service does not verify archived evidence path/hash.
- Ledger lacks explicit experiment spend total and spend-by-category APIs.
- Stale work-split documentation remains in repo.
```

## 5. Required Safety Invariants

After this remediation pass, the implementation must enforce these invariants.

### 5.1 Wallet Authorization Invariants

A wallet spend must not occur unless all of the following are true:

1. `spend_enabled == true`.
2. A spend request exists in the ledger before the send attempt.
3. The incoming request matches the ledger spend request.
4. The spend request is in an eligible pre-send status.
5. The linked policy decision exists.
6. The linked policy decision is exactly `allow`.
7. The linked policy decision was for an executable wallet/spend/purchase action.
8. The linked policy decision applies to the same opportunity/experiment/spend request.
9. The linked policy decision amount/category/counterparty/tool context is compatible with the spend.
10. The linked budget plan exists.
11. The linked budget plan is executable.
12. The linked budget plan explicitly permits wallet spend.
13. The requested amount is within the approved budget.
14. The linked TOS/legal check exists.
15. The linked TOS/legal check is exactly `proceed`.
16. The linked evidence artifacts exist.
17. The linked evidence artifacts are related to the opportunity, experiment, budget plan, or spend request.
18. Evidence artifact files exist on disk where applicable.
19. Evidence artifact hashes match where applicable.
20. The destination is valid for the configured asset/network.
21. The request does not express send-all/sweep/max/all-funds semantics.
22. The amount is positive.
23. The amount plus estimated fee is within single/daily/weekly limits.
24. The wallet has sufficient balance for amount plus fee.
25. The service records durable audit state before and after the attempted send.

### 5.2 Fail-Closed Invariants

The system must fail closed when:

- Policy metadata is missing.
- Policy action type is not executable.
- Incoming request IDs mismatch ledger IDs.
- Evidence IDs mismatch ledger spend request evidence IDs.
- Evidence files are missing or hashes do not match.
- Fee quote fails.
- Wallet unlock fails.
- Wallet send fails.
- Wallet lock fails.
- Budget decision is blocked or ambiguous.
- Budget references nonexistent policy/TOS records.
- Evidence archive input exceeds size limits.
- Evidence type is not filename-safe.
- BTC destination is malformed, including during quote.

### 5.3 Auditability Invariants

Every wallet spend attempt must be auditable, including rejected attempts.

For every attempted `send-small-payment`, the ledger/audit layer must preserve:

- request received event
- validation started event
- rejection event with structured reason code, if rejected
- backend send started event, if backend is reached
- backend success event, if successful
- backend failure event, if failed
- wallet lock failure event, if lock fails
- spend request status update
- sanitized request summary
- sanitized response summary
- related IDs

No audit event may include secrets.

## 6. Required Architecture Changes

## 6.1 Persist Policy Action Metadata

The service currently cannot prove whether a policy decision approved research, email drafting, purchasing, or wallet transfer.

Add persistent policy metadata sufficient for later service-side authorization.

### Required Policy Metadata

Each persisted policy decision must include, directly or through a linked request record:

```text
action_type
category
requires_payment
requires_wallet_action
amount_usd
counterparty
opportunity_id
experiment_id
spend_request_id, if applicable
planned_tools
policy_input_hash or raw sanitized input
```

The service must use this metadata to verify that the policy approval applies to the exact executable spend.

### Executable Wallet Action Types

The wallet service may accept policy decisions only for action types such as:

```text
SPEND
WALLET_TRANSFER
PURCHASE
```

Safe planning actions such as these must not authorize spend:

```text
RESEARCH
OPPORTUNITY_ANALYSIS
DRAFT_EMAIL
READ_ONLY_BROWSER
```

## 6.2 Reject Request/Ledger Mismatches

The wallet-governor service must compare incoming request fields against the ledger spend request.

The following mismatches must reject:

```text
policy_decision_id mismatch
budget_plan_id mismatch
evidence_archive_ids mismatch
amount mismatch
destination mismatch
category mismatch
counterparty mismatch, when present
purpose mismatch or materially inconsistent purpose
opportunity_id mismatch, when present
```

The service should use a structured reason code such as:

```text
spend_request_mismatch
```

or more specific reason codes if useful.

## 6.3 Update Spend Status on All Rejections

The current service does not update spend request status for early `spend_disabled` rejection because it rejects before loading the bundle.

Change the flow so that if `spend_request_id` is present, the service attempts to load it before early rejections and updates status where appropriate.

Eligible rejected status transitions:

```text
proposed -> rejected
approved -> rejected
sending -> failed
```

Do not mutate terminal statuses such as:

```text
sent
confirmed
failed
rejected
cancelled
```

except through explicit, valid transition APIs.

## 6.4 Validate Destination in Quote Path

`/quote-spend` must validate destination shape and send-all language just like `/send-small-payment`.

Quote must reject:

- missing destination
- malformed BTC address
- placeholder/test strings
- unsupported network address
- configured destination blocklist hits
- send-all/sweep/max/all-funds language

Quote must not unlock the wallet or send funds.

## 6.5 Convert Quote/Unlock/Backend Failures into Durable Rejections

The service must catch backend failures from:

```text
fee estimation
quote generation
wallet unlock
wallet send
wallet lock
transaction lookup, if part of send flow
```

Failure handling must:

- not crash the HTTP service
- return structured rejection/failure response
- record audit event
- update spend request status where appropriate
- avoid leaking secrets
- lock the wallet in a best-effort `finally` block when unlock may have succeeded

## 7. Budget Planner Required Changes

## 7.1 Decision Precedence

The budget planner currently can downgrade a hard rejection into `simulate` if later uncertainty checks run.

Implement explicit precedence:

```text
REJECT > HUMAN_REVIEW > SIMULATE > EXECUTE_REQUEST
```

If any hard rejection condition exists, the final decision must be `reject`.

Examples of hard rejection conditions:

- policy decision is not `allow`
- TOS/legal decision is not `proceed`
- spend exceeds max loss
- required references are missing
- prohibited category
- recurring costs are uncapped, if policy says reject
- invalid negative/zero economics

Examples of simulate conditions:

- revenue is unknown but no hard blockers exist
- expected return is uncertain but legal/policy checks are clear
- dry-run is recommended before spend

## 7.2 Graceful Missing Reference Handling

The planner must not crash with SQLite FK errors when given nonexistent policy or TOS IDs.

Before ledger insert:

- load policy record
- load TOS/legal record
- load opportunity record if referenced
- if required record is missing, return structured rejection or human-review result
- do not attempt to insert invalid FK rows

## 8. Evidence Archiver Required Changes

## 8.1 Enforce Size Limits for `content_text`

The archiver currently size-limits file input but not direct text input.

After converting `content_text` to bytes, enforce:

```text
len(content_bytes) <= max_artifact_bytes
```

Reject oversized text evidence with a clear error.

## 8.2 Strictly Sanitize Evidence Type

The archiver must not use weakly normalized evidence type strings in filenames.

Evidence type must be restricted to safe tokens, for example:

```regex
^[a-z0-9_]{1,64}$
```

Reject values containing:

- slash
- backslash
- dot-dot
- path separators
- null byte
- shell metacharacters
- whitespace after normalization if not expected
- very long strings

## 8.3 Evidence File and Hash Verification

The wallet service must not only check evidence IDs in the ledger. It must verify evidence artifacts where applicable:

- file exists
- file path resolves under archive root
- file is regular file
- file hash matches ledger metadata
- metadata file exists if required
- artifact relation matches spend/opportunity/experiment/budget context

This can be implemented in the wallet service or a shared evidence validation helper.

## 9. Ledger Required Changes

Add explicit APIs for:

```text
get_experiment_spend_total(experiment_id)
get_spend_by_category(...)
```

These APIs should count only real spend statuses, normally:

```text
sent
confirmed
```

They should exclude:

```text
proposed
approved
rejected
failed
cancelled
quote-only records
```

Add tests for both methods.

## 10. Documentation Required Changes

Remove or replace stale documentation that suggests splitting work between Copilot and OpenCode.

The current process is:

```text
Copilot and OpenCode should independently implement the same TODO from the same starting codebase.
```

The repo should not contain outdated instructions assigning wallet tasks to one agent and evidence/policy tasks to the other.

## 11. Non-Goals for This Pass

Do not implement the following in this pass unless already present and disabled:

- real wallet spending enabled by default
- real email sending enabled by default
- real browser automation
- unrestricted shell execution
- arbitrary Bitcoin RPC passthrough
- exchange API integration
- DeFi integration
- Solana/EVM wallet integration
- production deployment scripts that auto-enable spending

## 12. Test Requirements

The final implementation must include tests for:

- executable policy metadata required for wallet spend
- research policy cannot authorize wallet spend
- request/ledger policy ID mismatch rejected
- request/ledger budget ID mismatch rejected
- request/ledger evidence ID mismatch rejected
- spend-disabled updates existing spend request to rejected
- quote rejects malformed BTC destination
- fee quote failure records durable rejection
- unlock failure records durable rejection
- send failure records durable failure
- lock failure records audit event
- budget hard reject cannot become simulate
- missing policy/TOS references do not crash budget planner
- oversized `content_text` evidence rejected
- unsafe evidence type rejected
- missing evidence file rejected by wallet service
- evidence hash mismatch rejected by wallet service
- experiment spend total API works
- spend-by-category API works
- stale work-split docs removed or corrected

## 13. Acceptance Criteria

This remediation pass is complete when:

- all P0 findings from Code Review 2 are fixed
- all P1 findings from Code Review 2 are fixed or explicitly deferred with justification
- full test suite passes
- new regression tests cover every fixed issue
- wallet service can independently validate the full authorization chain
- real wallet spend remains disabled by default
- Bitcoin Core backend remains disabled by default
- no secrets are present in repo/test fixtures/docs
- stale parallel-agent documentation is corrected
- no code path can use research/email/draft policy approval to authorize wallet spend

## 14. Final Rule

Do not connect real BTC until this spec and the accompanying `CODE_REVIEW2_TODO.md` are implemented and reviewed.
