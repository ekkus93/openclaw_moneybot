# UNIT_TEST1_TODO.md

# OpenClaw MoneyBot — Unit Test Coverage Follow-up TODO

This TODO tracks the next focused unit-test pass after the current coverage review.

The goal is **not** to inflate coverage numbers mechanically. The goal is to add tests around:

- safety-critical rejection paths
- deterministic branching logic
- validator/model edge cases
- service/helper behavior that could silently drift

Current reference point from the latest coverage run:

```text
TOTAL: 89%
```

Highest-value uncovered areas:

- `skills/email_drafter/templates.py`
- `skills/email_drafter/compliance.py`
- `plugins/email_governor/service.py`
- `plugins/wallet_governor_service/service.py`
- `plugins/wallet_governor_service/backend.py`
- `skills/experiment_reviewer/decision.py`
- `orchestration/factory.py`

---

# Priority legend

```text
P0 = safety-critical service or validator gaps
P1 = important deterministic branching and model validation
P2 = secondary helper/config/factory coverage improvements
```

---

# 1. P0 — Expand Wallet Governor Service Rejection Coverage

## 1.1 Goal

Add direct unit tests for the remaining uncovered service-side wallet authorization branches in:

```text
src/openclaw_moneybot/plugins/wallet_governor_service/service.py
```

## 1.2 Spend-request and ledger-state branches

- [x] Add test: cached idempotent request with conflicting fingerprint returns `idempotency_conflict`.
- [x] Add test: unsupported asset reaches the `unsupported_asset` rejection path.
- [x] Add test: prior wallet transaction on the spend request returns `spend_request_status_invalid`.
- [x] Add test: ineligible spend-request status returns `spend_request_status_invalid`.
- [x] Add test: missing ledger prewrite context returns `spend_request_missing`.
- [x] Add test: mismatched `ledger_record_id` returns `spend_request_mismatch`.
- [x] Add test: mismatched `opportunity_id` returns `spend_request_mismatch`.
- [x] Add test: mismatched `counterparty` returns `spend_request_mismatch`.
- [x] Add test: mismatched `purpose` returns `spend_request_mismatch`.

## 1.3 Policy, budget, and TOS branches

- [x] Add test: missing policy in bundle returns `policy_missing`.
- [x] Add test: policy decision not `allow` returns `policy_not_allow`.
- [x] Add test: policy opportunity mismatch returns `policy_not_allow`.
- [x] Add test: missing budget returns `budget_missing`.
- [x] Add test: non-executable budget returns `budget_not_executable`.
- [x] Add test: budget with wallet spend disabled returns `budget_wallet_spend_not_allowed`.
- [x] Add test: budget opportunity mismatch returns `budget_not_executable`.
- [x] Add test: blank budget success metric returns `budget_not_executable`.
- [x] Add test: blank budget stop condition returns `budget_not_executable`.
- [x] Add test: approved spend categories excluding request category returns `budget_wallet_spend_not_allowed`.
- [x] Add test: missing TOS/legal check returns `tos_missing`.
- [x] Add test: TOS/legal opportunity mismatch returns `tos_not_proceed`.
- [x] Add test: TOS/legal record with no evidence IDs returns `evidence_missing`.

## 1.4 Category, evidence, and destination branches

- [x] Add test: blank category returns `category_missing`.
- [x] Add test: category blocked by built-in set returns `category_blocked`.
- [x] Add test: category blocked by policy config returns `category_blocked`.
- [x] Add test: unknown category returns `category_unknown`.
- [x] Add test: spend request with no evidence IDs returns `evidence_missing`.
- [x] Add test: unrelated evidence record returns `evidence_unrelated`.
- [x] Add test: blank destination returns `destination_missing`.
- [x] Add test: placeholder destination token returns `destination_invalid`.
- [x] Add test: prohibited send-all term in destination returns `send_all_blocked`.
- [x] Add test: prohibited send-all term in purpose returns `send_all_blocked`.
- [x] Add test: invalid BTC destination failing `_validate_destination()` returns `destination_invalid`.

## 1.5 Limit and helper branches

- [x] Add test: `_limit_rejection_code()` returns `amount_exceeds_single_limit`.
- [x] Add test: `_limit_rejection_code()` returns `amount_exceeds_daily_limit`.
- [x] Add test: `_limit_rejection_code()` returns `amount_exceeds_weekly_limit`.
- [x] Add test: `_require_supported_asset()` raises for unsupported asset.
- [x] Add test: `_validate_destination()` non-BTC branch accepts trimmed non-empty destination.
- [x] Add test: `_validate_destination()` non-BTC branch rejects blank destination.

## 1.6 JSON entrypoints and audit behavior

- [x] Add test: `quote_json()` rejects malformed payload through model validation.
- [x] Add test: `capped_send_json()` rejects malformed payload through model validation.
- [x] Add test: rejection path with `cache_response=False` does not mutate cached responses.
- [x] Add test: rejection path updates spend-request status to `rejected` only when bundle status is still eligible.

---

# 2. P0 — Expand Wallet Backend Failure and RPC Edge-Case Coverage

## 2.1 Goal

Cover the remaining failure-path branches in:

```text
src/openclaw_moneybot/plugins/wallet_governor_service/backend.py
```

## 2.2 Bitcoin Core config and parsing

- [x] Add test: `BitcoinCoreRpcConfig.from_env()` loads defaults correctly.
- [x] Add test: `BitcoinCoreRpcConfig.from_env()` parses `enabled=true`.
- [x] Add test: `get_balance_sats()` rejects malformed non-numeric balance payload.
- [x] Add test: `estimate_fee_sats()` rejects non-dict RPC payload.
- [x] Add test: `estimate_fee_sats()` rejects missing/non-numeric `feerate`.
- [x] Add test: `send_to_address()` rejects empty/non-string txid.
- [x] Add test: `get_transaction()` rejects non-dict result payload.

## 2.3 Unlock/lock and RPC error handling

- [x] Add test: `unlock()` raises if passphrase env var is configured but missing.
- [x] Add test: `unlock()` succeeds when passphrase env var is present.
- [x] Add test: `lock()` no-ops when passphrase support is disabled.
- [x] Add test: `_rpc()` rejects when backend is disabled.
- [x] Add test: `_rpc()` wraps HTTP transport failure as `WalletBackendError`.
- [x] Add test: `_rpc()` rejects non-object JSON response.
- [x] Add test: `_rpc()` rejects RPC error payload.

## 2.4 Fake backend edge cases

- [x] Add test: fake backend fee floor of 250 sats applies on tiny sends.
- [x] Add test: fake backend health payload shape remains stable.
- [x] Add test: fake backend `get_transaction()` returns backend tag and requested txid.

---

# 3. P0 — Expand Email Governor Send and Reply Branch Coverage

## 3.1 Goal

Add comprehensive unit coverage for remaining uncovered branches in:

```text
src/openclaw_moneybot/plugins/email_governor/service.py
src/openclaw_moneybot/plugins/email_governor/models.py
```

## 3.2 Send rejection matrix

- [x] Add test: missing draft returns `draft_missing`.
- [x] Add test: draft with no `opportunity_id` and no `related_experiment_id` returns `draft_unlinked`.
- [x] Add test: `related_opportunity_id` mismatch returns `draft_reference_mismatch`.
- [x] Add test: `related_experiment_id` mismatch returns `draft_reference_mismatch`.
- [x] Add test: missing policy decision returns `policy_missing`.
- [x] Add test: policy decision not `allow` returns `policy_not_allow`.
- [x] Add test: blocked draft risk flag returns `draft_risk_blocked`.
- [x] Add test: cold outreach without opt-out wording returns `opt_out_missing`.
- [x] Add test: daily sender cap returns `daily_rate_limit_exceeded`.
- [x] Add test: per-domain cap returns `domain_rate_limit_exceeded`.
- [x] Add test: previous `thread_opted_out` rejection blocks future send.

## 3.3 Reply classification branches

- [x] Add test: reply text with complaint keywords classifies as `complaint`.
- [x] Add test: reply text with decline keywords classifies as `rejection`.
- [x] Add test: reply text with positive keywords classifies as `positive`.
- [x] Add test: unmatched reply classifies as `needs_review`.
- [x] Add test: reply without `email_draft_id` archives against `RecordType.OPPORTUNITY`.
- [x] Add test: reply with only thread fallback still archives and audits correctly.

## 3.4 Internal helper behavior

- [x] Add test: `_iter_audit_payloads()` skips malformed non-dict payloads.
- [x] Add test: `_iter_audit_payloads(kind=...)` filters out mismatched kinds.
- [x] Add test: `_thread_has_opt_out()` returns true from inbound `opt_out`.
- [x] Add test: `_thread_has_opt_out()` returns true from prior `thread_opted_out` rejection.
- [x] Add test: `_thread_has_opt_out()` returns false for unrelated thread or recipient.

## 3.5 Model validation

- [x] Add test: `EmailSendRequest` rejects malformed `sender_email` with missing `@`.
- [x] Add test: `EmailSendRequest` rejects malformed `sender_email` with invalid domain.
- [x] Add test: `EmailReplyResult` accepted classifications remain constrained to the defined literal set.

---

# 4. P1 — Expand Email Drafter Template and Compliance Coverage

## 4.1 Goal

Cover the main deterministic branches in:

```text
src/openclaw_moneybot/skills/email_drafter/templates.py
src/openclaw_moneybot/skills/email_drafter/compliance.py
src/openclaw_moneybot/skills/email_drafter/models.py
```

## 4.2 Template rendering branches

- [x] Add test: `_recipient_line()` prefers `recipient_name`.
- [x] Add test: `_recipient_line()` falls back to `recipient_organization`.
- [x] Add test: `_recipient_line()` falls back to `"there"` when neither name nor org exists.
- [x] Add test: `_disclosure()` returns empty string when disclosure is off.
- [x] Add test: `_disclosure()` returns the automation notice when disclosure is on.
- [x] Add test: `render_template()` for `bounty_application` with explicit `source_url`.
- [x] Add test: `render_template()` for `bounty_application` without `source_url` uses fallback text.
- [x] Add test: `render_template()` for `vendor_question`.
- [x] Add test: `render_template()` for `receipt_request`.
- [x] Add test: `render_template()` for `followup`.
- [x] Add test: `render_template()` generic fallback path for unknown purpose.
- [x] Add test: each rendered template preserves stripped `context_summary` and `requested_call_to_action`.

## 4.3 Compliance branches

- [x] Add test: comma-separated recipient triggers `mass_recipient_request`.
- [x] Add test: `recipient_source_url` adds provenance note.
- [x] Add test: outbound purpose without `policy_decision_id` adds `missing_policy_approval`.
- [x] Add test: outbound purpose with non-allow policy adds `policy_not_allow`.
- [x] Add test: non-`proceed` TOS adds `tos_not_cleared`.
- [x] Add test: `max_followups > 1` adds `too_many_followups`.
- [x] Add test: `proposal` adds both commercial and cold-outreach notes.
- [x] Add test: affiliate text adds affiliate/referral note.
- [x] Add test: `bounty_application` adds bounty note.
- [x] Add test: `vendor_question` adds support note.
- [x] Add test: deceptive pattern in context or claims adds `deceptive_claim_pattern`.
- [x] Add test: scraped language adds `scraped_recipient_source`.
- [x] Add test: harassment-loop language adds `harassment_loop_pattern`.
- [x] Add test: allowed claim containing “guarantee” adds `unsupported_earnings_claim`.
- [x] Add test: `forbidden_claims` adds omission note.
- [x] Add test: `automation_disclosure_required` adds disclosure note.
- [x] Add test: combined-risk scenario returns all expected flags without silently dropping any.

## 4.4 Draft request validation

- [x] Add test: `EmailDraftRequest` rejects non-`draft_only` mode.
- [x] Add test: `EmailDraftRequest` rejects empty `context_summary`.
- [x] Add test: `EmailDraftRequest` rejects missing opportunity/experiment reference.
- [x] Add test: outbound purpose rejects missing `policy_decision_id`.
- [x] Add test: sender/recipient email validators reject malformed domains.

---

# 5. P1 — Expand Experiment Reviewer Decision Matrix Coverage

## 5.1 Goal

Cover the remaining uncovered decision branches in:

```text
src/openclaw_moneybot/skills/experiment_reviewer/decision.py
```

## 5.2 Missing decision-path tests

- [x] Add test: repeated-failures incident returns `BLOCK_CATEGORY`.
- [x] Add test: human-review flags (`complaint`, `payment_dispute`, `privacy_issue`) return `HUMAN_REVIEW`.
- [x] Add test: final ambiguous branch with spend above low-cost threshold returns `HUMAN_REVIEW` and `insufficient_data`.
- [x] Add test: verify the returned lessons and next-actions text for each of the above branches.
- [x] Add test: verify blocklist/policy-feedback output for repeated-failures path.

---

# 6. P1 — Expand Wallet HTTP Client and App Edge-Case Coverage

## 6.1 Goal

Add targeted unit tests for:

```text
src/openclaw_moneybot/plugins/wallet_governor_service/http.py
src/openclaw_moneybot/skills/wallet_governor_client/client.py
src/openclaw_moneybot/skills/wallet_governor_client/validation.py
```

## 6.2 HTTP app coverage

- [x] Add test: request timeout middleware returns HTTP 504.
- [x] Add test: `ValueError` handler returns HTTP 400 payload.
- [x] Add test: `WalletBackendError` handler returns HTTP 502 payload.
- [x] Add test: `ValidationError` handler returns HTTP 422 payload.
- [x] Add test: `/health` includes version and backend mode fields.
- [x] Add test: `/balance` includes `network` and `spend_enabled`.

## 6.3 HTTP client coverage

- [x] Add test: client retries retryable GET on timeout and eventually succeeds.
- [x] Add test: client raises `WalletGovernorClientError` on non-object JSON payload.
- [x] Add test: client raises `WalletGovernorClientError` on HTTP status error.
- [x] Add test: client raises `wallet governor unavailable` after retry exhaustion.
- [x] Add test: `close()` closes underlying client cleanly.

## 6.4 Client-side validation coverage

- [x] Add test: unsupported asset is reported by `validate_spend_request()`.
- [x] Add test: unsupported spend category is reported.
- [x] Add test: blocked spend category is reported.
- [x] Add test: invalid destination is reported.
- [x] Add test: missing evidence reference is reported.
- [x] Add test: send-all language in purpose is reported.
- [x] Add test: daily cap overflow is reported.
- [x] Add test: weekly cap overflow is reported.

---

# 7. P2 — Expand Browser Governor Coverage

## 7.1 Goal

Add the remaining lower-priority but useful tests for:

```text
src/openclaw_moneybot/plugins/browser_governor/service.py
```

## 7.2 Additional branches

- [x] Add test: non-allowlisted profile returns `profile_not_allowlisted`.
- [x] Add test: `uses_bot_evasion=True` returns `bot_evasion_blocked`.
- [x] Add test: `mass_signup=True` returns `mass_signup_blocked`.
- [x] Add test: `scraping_against_terms=True` returns `scraping_against_terms_blocked`.
- [x] Add test: purchase action with missing spend request returns `spend_request_missing`.
- [x] Add test: missing opportunity returns `opportunity_missing`.
- [x] Add test: missing policy returns `policy_missing`.
- [x] Add test: non-allow policy returns `policy_not_allow`.
- [x] Add test: `complete_action()` while governor disabled returns `browser_disabled`.
- [x] Add test: prepare payload lookup ignores unrelated audit events.

---

# 8. P2 — Expand Config, Factory, and Shared Validator Coverage

## 8.1 Goal

Cover remaining small but important validator/factory gaps in:

```text
src/openclaw_moneybot/shared/config.py
src/openclaw_moneybot/shared/base.py
src/openclaw_moneybot/orchestration/factory.py
```

## 8.2 Config validator coverage

- [x] Add test: wallet config rejects unsupported URL scheme.
- [x] Add test: email config rejects empty `allowed_sender_emails`.
- [x] Add test: email config rejects `capped_send` with non-positive `max_outbound_per_day`.
- [x] Add test: browser governor config rejects empty profile list.
- [x] Add test: config loader rejects non-mapping root.
- [x] Add test: config loader reports structured validation errors for missing nested sections.

## 8.3 Shared/base validator coverage

- [x] Add test: `TimestampedModel` rejects naive datetime values.

## 8.4 Orchestration factory coverage

- [x] Add test: `build_orchestrator()` returns a `MoneyBotOrchestrator`.
- [x] Add test: `build_orchestrator()` wires all expected component types.
- [x] Add test: `build_orchestrator()` passes the optional wallet transport into `WalletGovernorClientSkill`.
- [x] Add test: factory-created ledger path exists and is migrated.

---

# 9. P2 — Secondary Backlog from Coverage Report

These are useful, but lower priority than the items above.

Deferred after this pass because the targeted safety-critical modules are now covered at 94-99%, total repository coverage reached 95%, and the remaining misses are concentrated in lower-risk helper branches outside the original target set.

- [ ] Add more repository/service tests for rarely-hit ledger helper branches in `skills/ledger_skill/repository.py`.
- [ ] Add model validator edge-case tests for `budget_and_roi_planner/models.py`.
- [ ] Add additional rule-path tests in `moneybot_policy_guard/rules.py` for currently unhit prerequisite branches.
- [ ] Add more negative-model tests for `receipt_and_evidence_archiver/models.py`.

---

# 10. Test helper and fixture work

## 10.1 Reusable helpers

- [ ] Extract shared fixtures/builders for:
  - [ ] policy decisions
  - [ ] draft email records
  - [ ] audit ledger events
  - [ ] wallet spend bundles
  - [ ] fake RPC responses
- [x] Add helper utilities for mutating one field at a time in wallet/email request objects.
- [x] Add helper to seed malformed audit-event payloads safely for iterator tests.

Shared fixture extraction is deferred for now: the pass added narrowly scoped local helpers where needed, but a broad cross-file helper refactor would add churn without improving the targeted safety coverage materially.

## 10.2 Test quality rules

- [x] Keep tests offline and deterministic.
- [x] Do not connect to live Bitcoin Core.
- [x] Do not send real email.
- [x] Do not add browser automation or external browsing.
- [x] Prefer narrow, one-branch-per-test coverage where rejection code identity matters.
- [x] Assert exact rejection reasons for safety-critical paths.
- [x] Assert audit/evidence side effects where services promise durable records.

---

# 11. Recommended implementation order

1. **P0 wallet governor service + backend**
2. **P0 email governor service**
3. **P1 email templates + compliance**
4. **P1 experiment reviewer decision**
5. **P1 wallet HTTP/client validation**
6. **P2 browser governor**
7. **P2 config/factory/shared validators**
8. **P2 secondary backlog**

---

# 12. Acceptance criteria

This TODO is complete when:

- [x] All listed P0 unit tests are implemented.
- [x] All listed P1 unit tests are implemented.
- [x] P2 items are either implemented or explicitly deferred with rationale.
- [x] Safety-critical services assert exact rejection codes and durable side effects.
- [x] Coverage improves meaningfully in the targeted modules, especially:
  - [x] `wallet_governor_service/service.py`
  - [x] `wallet_governor_service/backend.py`
  - [x] `email_governor/service.py`
  - [x] `email_drafter/templates.py`
  - [x] `email_drafter/compliance.py`
- [x] `uv run --python 3.11 ruff check .` passes.
- [x] `uv run --python 3.11 mypy .` passes.
- [x] `uv run --python 3.11 pytest` passes.
