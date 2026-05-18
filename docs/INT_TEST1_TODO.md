# INT_TEST1_TODO.md

# OpenClaw MoneyBot — Integration Test Follow-up TODO

This TODO tracks the next focused **integration-test** pass after the recent unit-test expansion.

The goal is **not** to add broad end-to-end coverage for its own sake. The goal is to add integration tests around:

- fail-closed workflow behavior across multiple skills
- real handoff boundaries between orchestrator, governors, ledger, and evidence archive
- durable-record and evidence-linkage guarantees
- idempotency and replay safety across governed actions
- local client/server integration at the wallet boundary

Current reference point:

```text
Existing integration coverage is concentrated in tests/integration/test_workflow.py:
- one dry-run workflow trail
- one wallet fail-closed path
- one tiny capped payment success path
```

Highest-value missing integration areas:

- workflow stops when policy/TOS/budget decisions block or require review
- governed email send/reply flow with durable audit and archive side effects
- wallet client talking to the local HTTP wrapper instead of an in-memory transport shim
- browser governor prepare/complete integration against real ledger and evidence services
- experiment review outcomes driven by actual prior workflow artifacts
- replay/idempotency behavior across wallet/email/browser governed actions
- full evidence and ledger linkage checks across one multi-stage mission

---

# Priority legend

```text
P0 = safety-critical workflow and governor boundary tests
P1 = important cross-skill orchestration and durable-record tests
P2 = replay, audit, and secondary regression integration tests
```

---

# 1. P0 — Expand Fail-Closed Workflow Gate Coverage

## 1.1 Goal

Add integration tests around the default orchestration workflow in:

```text
tests/integration/test_workflow.py
src/openclaw_moneybot/orchestration/workflow.py
```

The focus is proving that the workflow **stops safely** when one of the required gates fails.

## 1.2 Initial policy gate failures

- [x] Add test: initial policy decision of `block` stops the workflow before TOS/legal, budget, email, wallet, and review execution.
- [x] Add test: initial policy decision of `needs_review` stops the workflow before downstream autonomous actions.
- [x] In each case, assert:
  - [x] the opportunity record is written
  - [x] the initial policy record is written
  - [x] no downstream budget, email, wallet transaction, or experiment review execution record is created
  - [x] evidence from the scouting/source stage remains archived

## 1.3 TOS/legal gate failures

- [x] Add test: TOS/legal decision of `reject` stops downstream budget, email, wallet, and review execution.
- [x] Add test: TOS/legal decision of `human_review` stops downstream autonomous execution.
- [x] In each case, assert:
  - [x] the TOS/legal ledger record exists
  - [x] downstream execution-adjacent records do not exist
  - [x] the timeline clearly ends at the gating step

## 1.4 Budget gate failures

- [x] Add test: budget planner returns non-executable output and the workflow stops before email and wallet execution.
- [x] Add test: budget plan with wallet handoff absent still allows non-wallet dry-run review behavior where appropriate.
- [x] In each case, assert:
  - [x] the budget record is written
  - [x] no wallet spend request or wallet transaction is created
  - [x] no unsafe side effects occur after the budget stop

## 1.5 Execution policy recheck failures

- [x] Add test: initial policy allows the mission, but execution policy blocks the concrete plan and stops email/wallet execution.
- [x] Add test: execution policy returns `needs_review` and the workflow fails closed.
- [x] Assert exact point of stop in the timeline and the absence of later execution records.

---

# 2. P0 — Add Wallet Client <-> Local HTTP Wrapper Integration Tests

## 2.1 Goal

Test the real boundary between:

```text
src/openclaw_moneybot/plugins/wallet_governor_service/http.py
src/openclaw_moneybot/skills/wallet_governor_client/runner.py
src/openclaw_moneybot/skills/wallet_governor_client/client.py
```

Use the actual FastAPI app in-process instead of a path-switching transport helper that bypasses the wrapper behavior.

## 2.2 Read-only local service integration

- [x] Add integration test: wallet client `get_balance()` succeeds against the real local FastAPI app.
- [x] Add integration test: wallet client `quote()` succeeds against the real local FastAPI app.
- [x] Assert:
  - [x] returned payloads include HTTP-wrapper-added metadata such as `network`, `spend_enabled`, or `backend_mode` where expected
  - [x] the client correctly normalizes the service response

## 2.3 Governed send integration

- [x] Add integration test: wallet client `spend()` succeeds through the real HTTP wrapper with spend enabled.
- [x] Add integration test: wallet client `spend()` returns a governed rejection through the real HTTP wrapper when spend is disabled.
- [x] Add integration test: wallet client `spend()` surfaces service-side validation rejection reasons unchanged through the real wrapper.
- [x] Assert:
  - [x] spend request is written before send
  - [x] wallet transaction exists only on successful send
  - [x] response payload evidence is archived
  - [x] audit events are written for rejected and error outcomes

## 2.4 Local wrapper error translation

- [x] Add integration test: malformed request sent by the client path results in a safe client-visible error.
- [x] Add integration test: backend failure through the wrapper becomes a safe client error result, not a crash.
- [x] Add integration test: timeout path through the wrapper becomes a safe client error result.
- [x] Assert durable error evidence and audit trail behavior for those paths.

---

# 3. P0 — Add Email Governor End-to-End Integration Tests

## 3.1 Goal

Exercise the real flow across:

```text
src/openclaw_moneybot/skills/email_drafter/
src/openclaw_moneybot/plugins/email_governor/
src/openclaw_moneybot/skills/ledger_skill/
src/openclaw_moneybot/skills/receipt_and_evidence_archiver/
```

The focus is proving that draft generation, governed send, and reply classification remain linked through durable records.

## 3.2 Draft-to-send happy path

- [x] Add integration test: create an email draft and successfully send it through `EmailGovernorService`.
- [x] Assert:
  - [x] the draft record exists
  - [x] the send audit event exists
  - [x] outbound message evidence is archived
  - [x] the send references the correct opportunity or experiment
  - [x] sender allowlist and policy approval are enforced through the real service boundary

## 3.3 Draft-to-send blocked path

- [x] Add integration test: valid draft exists, but policy decision blocks send and the send is rejected.
- [x] Add integration test: cold outreach draft without opt-out wording is rejected in the end-to-end flow.
- [x] Add integration test: a thread previously marked opted out blocks a later send on the same thread.
- [x] Assert:
  - [x] rejection reason is exact
  - [x] rejection audit event exists
  - [x] no false success evidence or message id is recorded

## 3.4 Reply classification integration

- [x] Add integration test: send a governed outbound email, then process a positive inbound reply and assert durable linkage.
- [x] Add integration test: send a governed outbound email, then process an opt-out reply and assert future send attempts are blocked.
- [x] Add integration test: complaint reply is archived and auditable against the same thread.
- [x] Assert:
  - [x] reply evidence is archived
  - [x] reply audit event exists
  - [x] follow-on send behavior changes when opt-out state exists

---

# 4. P1 — Add Browser Governor Integration Tests

## 4.1 Goal

Exercise real prepare/complete flows across:

```text
src/openclaw_moneybot/plugins/browser_governor/
src/openclaw_moneybot/skills/ledger_skill/
src/openclaw_moneybot/skills/receipt_and_evidence_archiver/
```

These tests should remain **governor-only** and must not introduce live automation.

## 4.2 Approved prepare/complete flow

- [x] Add integration test: approved browser action prepare writes before-evidence and audit state, then completion writes after-evidence and completion audit state.
- [x] Assert:
  - [x] before/after evidence records exist
  - [x] both audit events exist
  - [x] completion reuses the prepared action state correctly

## 4.3 Blocked browser action flow

- [x] Add integration test: purchase action without a linked spend request is rejected end-to-end.
- [x] Add integration test: non-allow policy prevents prepare and no evidence is archived beyond rejection audit state.
- [x] Add integration test: disabled browser governor blocks both prepare and complete paths consistently.
- [x] Assert exact rejection reasons and durable audit behavior.

## 4.4 Ledger-linkage checks

- [x] Add integration test: prepared browser action is discoverable via related audit events and linked evidence records.
- [x] Add integration test: unrelated audit events do not corrupt prepare/complete matching.

---

# 5. P1 — Add Experiment Review Feedback-Loop Integration Tests

## 5.1 Goal

Exercise the real path from execution artifacts into review outcomes across:

```text
src/openclaw_moneybot/skills/experiment_reviewer/
src/openclaw_moneybot/skills/ledger_skill/
src/openclaw_moneybot/orchestration/workflow.py
```

## 5.2 Review after profitable execution

- [x] Add integration test: workflow produces a successful bounded execution trail, then experiment review records a `CONTINUE` outcome.
- [x] Assert:
  - [x] review record exists in the ledger
  - [x] review evidence is archived
  - [x] review text/feedback reflects the actual prior workflow artifacts

## 5.3 Review after costly ambiguous execution

- [x] Add integration test: spend occurs, evidence is weak or incomplete, and review returns `HUMAN_REVIEW`.
- [x] Add integration test: repeated failures or explicit incident flags produce the expected higher-severity review outcome.
- [x] Assert:
  - [x] review decision matches actual spend/evidence/incident conditions
  - [x] review output is linked to the correct opportunity and budget context

---

# 6. P1 — Add Evidence and Ledger Linkage Regression Tests

## 6.1 Goal

Prove that one realistic multi-stage mission leaves a complete and traceable record across:

- opportunity
- policy decisions
- TOS/legal checks
- budget
- email draft or browser prepare
- wallet quote/spend results when applicable
- evidence artifacts
- experiment review

## 6.2 Cross-record traceability

- [x] Add integration test: one multi-stage mission leaves ledger entries and evidence artifacts that can be traced by `opportunity_id`.
- [x] Assert:
  - [x] every major stage produces either a ledger record, an evidence record, or both
  - [x] evidence records point to the correct related record types and ids
  - [x] the returned workflow timeline is consistent with persisted ledger data

## 6.3 No hidden side effects

- [x] Add integration test: a blocked mission still leaves a visible audit/evidence trail for the attempted path, but no hidden execution-side durable records.
- [x] Assert absence of wallet transactions, browser completions, or send-success records when the workflow blocks earlier.

---

# 7. P2 — Add Replay and Idempotency Integration Tests

## 7.1 Goal

Prove that governed operations remain replay-safe when the same request is repeated.

## 7.2 Wallet replay behavior

- [x] Add integration test: repeat the same governed wallet send request and assert no duplicate durable wallet transaction record is created.
- [x] Add integration test: replay with the same idempotency key but conflicting payload is rejected safely.
- [x] Assert:
  - [x] cached response or conflict behavior is deterministic
  - [x] no duplicate spend-side durable records appear

## 7.3 Email replay behavior

- [x] Add integration test: repeat the same email send request and assert no duplicate outbound durable success path is recorded.
- [x] Add integration test: prior rejection/audit state is handled deterministically on replay.

## 7.4 Browser replay behavior

- [x] Add integration test: repeated completion attempt for the same browser action does not create inconsistent duplicate completion artifacts.
- [x] Add integration test: repeated prepare with the same action id remains safely auditable.

---

# 8. P2 — Add Local Service Boundary Regression Tests

## 8.1 Goal

Add a small set of integration tests that ensure the local-only safety assumptions stay intact.

## 8.2 Local-only assumptions

- [x] Add integration test: wallet service app rejects non-local bind host when built in an integration fixture.
- [x] Add integration test: wallet client configured against localhost still behaves correctly with the in-process app boundary.
- [x] Add integration test: no integration test requires live network, live Bitcoin Core, real email, or browser automation.

## 8.3 Fixture discipline

- [x] Ensure all integration fixtures remain deterministic and offline.
- [x] Reuse fake backends and in-process apps instead of external daemons.
- [x] Keep test data self-contained under `tests/fixtures/` where reusable content is needed.

---

# 9. Suggested fixture and helper work

## 9.1 Shared integration builders

- [x] Extract helper/builder for a standard local integration ledger + archive setup.
- [x] Extract helper for a standard wallet governor service + in-process FastAPI app.
- [x] Extract helper for a seeded opportunity/policy/TOS/budget trail.
- [x] Extract helper for governed email send/reply setup.
- [x] Extract helper for browser-governor prepare/complete setup.

## 9.2 Test ergonomics

- [x] Keep integration assertions focused on boundary behavior, not internal implementation details.
- [x] Prefer one scenario per test when exact stopping point or rejection identity matters.
- [x] When a scenario covers many stages, add assertions for both returned results and persisted durable state.

---

# 10. Recommended implementation order

1. **P0 fail-closed workflow gates**
2. **P0 wallet client <-> local HTTP wrapper**
3. **P0 email governor end-to-end**
4. **P1 browser governor integration**
5. **P1 experiment review feedback loop**
6. **P1 evidence and ledger linkage regression**
7. **P2 replay and idempotency coverage**
8. **P2 local service boundary regression**
9. **shared integration fixture cleanup**

---

# 11. Acceptance criteria

This TODO is complete when:

- [x] The existing workflow integration coverage is expanded beyond the current three scenarios.
- [x] Fail-closed behavior is covered for policy, TOS/legal, budget, and execution-policy gates.
- [x] Wallet client/server integration is tested across the real local HTTP wrapper boundary.
- [x] Governed email send/reply flow is tested end-to-end with durable audit and evidence checks.
- [x] Browser governor prepare/complete flow is tested without introducing live automation.
- [x] Experiment review outcomes are tested against actual prior workflow artifacts.
- [x] Replay/idempotency behavior is tested for wallet, email, or browser governed actions.
- [x] Multi-stage ledger/evidence linkage assertions prove auditability across one realistic mission.
- [x] All new integration tests remain offline and deterministic.
- [x] `uv run --python 3.11 ruff check .` passes after the integration-test pass.
- [x] `uv run --python 3.11 mypy .` passes after the integration-test pass.
- [x] `uv run --python 3.11 pytest` passes after the integration-test pass.
