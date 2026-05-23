# INT_TEST3_TODO.md

# OpenClaw MoneyBot - Integration Test Follow-up TODO 3

This TODO tracks the next focused **integration-test** pass after the current workflow, governor, skill-wave, plugin-wave, and UNIT_TEST3 coverage work.

The goal is **not** to add broad end-to-end tests mechanically. The goal is to add realistic local-only coverage around:

- real pre-execution disagreement handling across the orchestrator, `inner_voice_plugin`, and `arbiter`
- fail-closed workflow behavior when disagreement outcomes or follow-up requirements intersect with spend and execution paths
- recheck behavior when prior approved artifacts exist but newer rules, evidence, or workflow state require a fresh stop/review decision
- real service-boundary behavior for the remaining hosted research/discovery plugins
- end-to-end observability and metrics persistence for the inner-voice review/debate/Arbiter stack

Current reference point:

```text
Existing integration coverage already exercises:
- workflow gate and wallet paths
- email governor and browser governor service boundaries
- wallet HTTP wrapper integration
- skill-wave and plugin-wave boundaries
- inner-voice review checkpoints plus several disagreement interpretation scenarios
```

Highest-value missing integration areas:

- full orchestrator -> debate coordinator -> Arbiter execution on a real spend-path disagreement
- execution-adjacent `proceed_with_followups` and Arbiter outcomes proving the workflow still fails closed where required
- recheck/stop behavior when prior planning artifacts exist but later evidence or rule changes should block reuse
- Brave, Mastodon, and crypto market plugin service boundaries with archive + ledger linkage proven in integration rather than only unit tests
- observability helpers and metrics snapshots built from realistic persisted inner-voice records rather than mostly unit-shaped fixtures

---

# Priority legend

```text
P0 = safety-critical orchestration and fail-closed disagreement integration
P1 = important plugin-boundary and durable-observability integration
P2 = replay, audit, and secondary regression integration coverage
```

---

# 1. P0 - Add Real Spend-Path Disagreement Workflow Integration Coverage

## 1.1 Goal

Exercise the real path where the default workflow reaches an execution-adjacent decision, invokes `InnerVoiceCoordinator`, runs a bounded debate, and if needed escalates to the Arbiter before the workflow decides whether to continue or stop.

Primary files likely involved:

```text
tests/integration/test_workflow.py
tests/integration/test_inner_voice_integration.py
src/openclaw_moneybot/orchestration/workflow.py
src/openclaw_moneybot/plugins/inner_voice_plugin/debate.py
src/openclaw_moneybot/plugins/inner_voice_plugin/arbiter.py
```

## 1.2 Debate happy-path wiring baseline

- [x] Add integration test: a spend-enabled workflow reaches a real pre-execution disagreement, the debate converges without Arbiter escalation, and the workflow returns the expected bounded status.
- [x] Assert:
  - [x] the debate session record exists
  - [x] transcript and summary evidence are archived
  - [x] the mission timeline or final result includes the resulting disagreement interpretation
  - [x] later workflow behavior matches the converged debate disposition instead of bypassing disagreement handling

## 1.3 Max-rounds -> Arbiter escalation path

- [x] Add integration test: a spend-enabled workflow reaches `max_debate_rounds`, invokes the Arbiter, and records the Arbiter result durably.
- [x] Add integration test: either OpenClaw or the inner voice requests Arbiter escalation explicitly and the Arbiter path is still exercised correctly.
- [x] Assert:
  - [x] the debate record links to the Arbiter review ID
  - [x] transcript archive IDs are passed through to the Arbiter request/result path
  - [x] Arbiter evidence and ledger records exist
  - [x] the workflow result reflects the Arbiter-backed interpretation rather than ignoring it

## 1.4 Required fail-closed spend-path behavior

- [x] Add integration test: debate/Arbiter result lands on `needs_review` for a spend path and the workflow stops before any spend execution.
- [x] Add integration test: debate/Arbiter result lands on `proceed_with_followups` for a spend path and the workflow still fails closed to review instead of auto-advancing.
- [x] Assert:
  - [x] no wallet spend request or wallet transaction is created
  - [x] no browser purchase or other execution-adjacent action occurs
  - [x] the stop stage and stop reason are durable and exact
  - [x] debate and Arbiter artifacts remain linked to the same subject/opportunity context

## 1.5 Deterministic gates still outrank model disagreement outcomes

- [x] Add integration test: a deterministic workflow gate is already blocking, but a debate or Arbiter outcome would otherwise allow proceeding; the deterministic block still wins.
- [x] Add integration test: deterministic `needs_review` survives a debate/Arbiter `adopt_openclaw` or `proceed` style resolution.
- [x] Assert:
  - [x] final workflow status matches the deterministic gate
  - [x] disagreement records still persist for auditability
  - [x] no downstream autonomous execution bypasses the deterministic block

---

# 2. P0 - Add Prior-Artifact Recheck and Stale-Approval Workflow Integration Coverage

## 2.1 Goal

Exercise workflow behavior when prior budget/policy/evidence context exists, but newer state should force a recheck or fail-closed stop instead of silently reusing stale approval.

Primary files likely involved:

```text
tests/integration/test_workflow.py
tests/integration/test_inner_voice_integration.py
tests/integration/test_plugin_phase_a_integration.py
src/openclaw_moneybot/orchestration/workflow.py
src/openclaw_moneybot/skills/terms_change_monitor/
src/openclaw_moneybot/plugins/rules_snapshot_gateway/
```

## 2.2 Prior-approved baseline

- [x] Add integration test: a mission with prior approved planning artifacts can still proceed when the refreshed rules/evidence state is materially unchanged.
- [x] Assert:
  - [x] prior artifact references are preserved
  - [x] no false recheck/block state is introduced
  - [x] the workflow trail clearly distinguishes reused context from newly created records

## 2.3 Recheck-required path after prior plan exists

- [x] Add integration test: a mission has prior budget/policy context, then refreshed terms or evidence require budget or policy recheck before execution.
- [x] Add integration test: the workflow stops cleanly instead of reusing the old executable plan.
- [x] Assert:
  - [x] the stop or recheck reason is durable in the workflow result and ledger
  - [x] prior approval IDs remain linked for auditability
  - [x] no wallet, browser, email, or packaging execution happens after the recheck trigger

## 2.4 Inner-voice review against stale prior context

- [x] Add integration test: prior approved context plus stale evidence triggers an inner-voice disagreement path that ends in review rather than proceed.
- [x] Assert:
  - [x] the disagreement artifacts link back to the prior planning/review context
  - [x] the workflow does not silently downgrade the stale-evidence concern
  - [x] the final stop reason remains understandable and operator-facing

## 2.5 Replay-safety around recheck scenarios

- [x] Add integration test: re-running the same recheck-triggering path does not create misleading duplicate success-side execution artifacts.
- [x] Assert:
  - [x] repeated runs remain deterministic in final status
  - [x] duplicate records, if they exist, are limited to the expected new review/debate trail rather than unsafe execution side effects
  - [x] no stale prior execution approval leaks into the repeated run

---

# 3. P1 - Add Remaining Hosted Research/Discovery Plugin Boundary Integration Coverage

## 3.1 Goal

Cover the remaining plugin service boundaries where the main value is proving archive + ledger + audit linkage through the real plugin service layer with mocked transports.

Primary files likely involved:

```text
tests/integration/test_plugin_phase_c_integration.py
tests/integration/test_plugin_phase_b_integration.py
tests/integration/test_plugin_phase_a_integration.py
src/openclaw_moneybot/plugins/brave_search_plugin/
src/openclaw_moneybot/plugins/mastodon_discovery_plugin/
src/openclaw_moneybot/plugins/crypto_market_data_plugin/
```

## 3.2 Brave Search integration follow-up

- [x] Add integration test: successful Brave web search records the expected evidence snapshot and ledger record through the real plugin boundary.
- [x] Add integration test: Brave news-style lookup records the expected mode/freshness/source-domain linkage.
- [x] Add integration test: provider-side invalid response or rejection records the expected audit/error trail without false success evidence.
- [x] Assert:
  - [x] evidence archive content matches request/response shape
  - [x] ledger payloads keep the expected search mode metadata
  - [x] disabled or misconfigured paths remain fail-closed

## 3.3 Mastodon discovery integration follow-up

- [x] Add integration test: timeline sampling through the real Mastodon plugin boundary records normalized results, evidence, and ledger linkage.
- [x] Add integration test: malformed provider response or transport failure records the expected failure audit event without false discovery output.
- [x] Assert:
  - [x] normalized author/tag/link data is preserved in the result summary
  - [x] archived raw response evidence exists
  - [x] failure paths do not write misleading successful discovery records

## 3.4 Crypto market data integration follow-up

- [x] Add integration test: spot price lookup records evidence and ledger state through the real plugin service.
- [x] Add integration test: market-chart lookup records bounded recent points and archive linkage.
- [x] Add integration test: provider-side rate-limit or malformed payload response fails closed with durable audit behavior.
- [x] Assert:
  - [x] no trading authority or spend-side records are created
  - [x] evidence types and record types are exact
  - [x] provider error messaging remains visible and bounded

## 3.5 Cross-plugin consistency checks

- [x] Add integration assertion set proving the remaining research/discovery plugins all preserve the expected pattern:
  - [x] disabled-by-default behavior
  - [x] evidence archival on success
  - [x] durable ledger linkage on success
  - [x] explicit safe failure behavior on transport/provider errors

---

# 4. P1 - Add Inner-Voice Observability and Metrics Integration Coverage

## 4.1 Goal

Prove the full persistence/query/reporting path for inner-voice review, debate, Arbiter, and metrics artifacts works correctly against real ledger data.

Primary files likely involved:

```text
tests/integration/test_inner_voice_integration.py
tests/integration/test_workflow.py
src/openclaw_moneybot/plugins/inner_voice_plugin/observability.py
src/openclaw_moneybot/plugins/inner_voice_plugin/debate.py
src/openclaw_moneybot/plugins/metrics_export_plugin/
```

## 4.2 Persisted review/debate/Arbiter query coverage

- [x] Add integration test: create real inner-voice review, debate, and Arbiter records, then query them back through the observability helpers.
- [x] Assert:
  - [x] subject, stage, and outcome filters all work against persisted ledger data
  - [x] disagreement records expose the expected `resolution_outcome`
  - [x] unrelated records are excluded cleanly

## 4.3 Metrics snapshot persistence from real records

- [x] Add integration test: produce realistic review/debate/Arbiter records, build a metrics snapshot, and persist it through the archive/ledger path.
- [x] Assert:
  - [x] the metrics export record exists
  - [x] archived metrics evidence exists
  - [x] snapshot counts reflect the actual generated records rather than fixture-only assumptions

## 4.4 Workflow-generated observability trail

- [x] Add integration test: a workflow-run disagreement path leaves a complete observability trail that can be queried after the mission completes or stops.
- [x] Assert:
  - [x] review/debate/Arbiter records all remain discoverable by the shared subject/opportunity context
  - [x] transcript and summary archives can be matched back to the persisted records
  - [x] the workflow result’s inner-voice IDs are consistent with the observability queries

## 4.5 Metrics/export regression path

- [x] Add integration test: mixed success/review/failure inner-voice history produces a bounded metrics export without crashing or silently dropping partial records.
- [x] Assert:
  - [x] malformed or partial provider summaries do not break export generation
  - [x] expected rates and counts remain deterministic
  - [x] archive + ledger linkage survives mixed-quality historical data

---

# 5. P2 - Add Debate/Arbiter Replay and Audit Regression Integration Coverage

## 5.1 Goal

Add secondary regression coverage around repeated disagreement handling runs and their audit behavior so later refactors do not create duplicate success-shaped artifacts or inconsistent audit trails.

Primary files likely involved:

```text
tests/integration/test_inner_voice_integration.py
tests/integration/test_workflow.py
src/openclaw_moneybot/plugins/inner_voice_plugin/debate.py
src/openclaw_moneybot/orchestration/workflow.py
```

## 5.2 Repeat disagreement run behavior

- [x] Add integration test: the same debate-triggering mission is executed twice and both runs remain deterministic in end state.
- [x] Assert:
  - [x] each run leaves a bounded review/debate trail
  - [x] no duplicate wallet/browser/email execution artifacts are created on fail-closed paths
  - [x] repeated disagreement handling does not mutate prior archived transcript/summary content

## 5.3 Audit event consistency

- [x] Add integration test: a successful converged debate path records the expected start/completion audit events.
- [x] Add integration test: an Arbiter invocation failure path records escalation-request plus failure audit events with the expected linkage.
- [x] Add integration test: orchestrator-escalated disagreement path records the expected escalation audit event.
- [x] Assert:
  - [x] event names are exact
  - [x] event payloads include the expected subject/stage/reason fields
  - [x] no misleading completion event appears on failed disagreement runs

## 5.4 Transcript and summary regression checks

- [x] Add integration test: raw transcript archival disabled path still archives the expected placeholder while preserving summary linkage.
- [x] Add integration test: transcript metadata enabled/disabled branches remain stable in the archived output shape.
- [x] Assert:
  - [x] no hidden transcript content leaks into placeholder-only archival
  - [x] summary linkage remains intact even when transcript raw content is disabled

---

# 6. P2 - Final Validation and Gap Review

## 6.1 Implementation checklist

- [x] Add or update the relevant integration test modules for each targeted boundary.
- [x] Keep all new tests local-only with mocked transports, fake services, or in-process FastAPI apps.
- [x] Prefer realistic cross-module boundaries over duplicating unit-level parser checks.
- [x] Avoid live hosted APIs, live browser automation, and live wallet/email side effects.

## 6.2 Validation checklist

- [x] Run `uv run --python 3.11 ruff check .`
- [x] Run `uv run --python 3.11 mypy .`
- [x] Run `uv run --python 3.11 pytest`
- [x] Re-review the highest-risk orchestration and plugin boundaries after the INT_TEST3 pass.
- [x] Decide whether any additional integration work is still justified versus leaving the remaining gaps to unit coverage.
