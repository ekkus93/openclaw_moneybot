# INT_TEST2_TODO.md

# OpenClaw MoneyBot - Integration Test Follow-up TODO 2

This TODO tracks the next focused **integration-test** pass after the current workflow, wallet, governor, skill-wave, and plugin-wave coverage.

The goal is **not** to add broad integration tests mechanically. The goal is to add realistic local-only coverage around:

- fail-closed workflow stops driven by the new skills
- recheck behavior when rules or terms drift after planning
- deterministic handoffs from package-building to rendering, archive, and ledger
- quarantine and evidence-promotion boundaries before downstream use
- multi-step payout reconciliation and follow-up planning flows
- counterparty due-diligence signals crossing plugin/skill boundaries
- metrics exports generated from realistic experiment history
- replay and idempotency safety across newly added skills and plugins

Current reference point:

```text
Existing integration coverage already exercises:
- workflow gate and wallet paths
- email governor and browser governor service boundaries
- wallet HTTP wrapper integration
- the newer skills wave
- plugin phase A/B/C boundaries
```

Highest-value missing integration areas:

- eligibility-driven workflow stop behavior before planning/execution
- rules-change recheck propagation after a previously approved plan exists
- submission-package -> artifact-renderer -> archive -> ledger traceability
- quarantine promotion as the only safe path into downstream evidence use
- observed payouts flowing into reconciliation and follow-up planning
- counterparty snapshot + risk profiling affecting downstream planning state
- metrics export against realistic mixed ledger history rather than isolated fixtures
- replay/idempotency across the newer packaging, reconciliation, and export paths

---

# Priority legend

```text
P0 = safety-critical workflow gating and state-transition integration
P1 = important cross-skill/plugin handoff and audit-trace integration
P2 = replay, export, and secondary regression integration coverage
```

---

# 1. P0 - Add Eligibility-Gated Workflow Integration Coverage

## 1.1 Goal

Add integration tests proving that the newer account eligibility gate can stop a mission safely before any planning or execution-adjacent side effects.

Primary files likely involved:

```text
tests/integration/test_workflow.py
tests/integration/test_new_skills_integration.py
src/openclaw_moneybot/orchestration/workflow.py
src/openclaw_moneybot/skills/account_eligibility_checker/
```

## 1.2 Happy-path wiring baseline

- [x] Add integration test: workflow path records an eligibility result and continues when the profile satisfies the opportunity rules.
- [x] Assert:
  - [x] the opportunity record exists
  - [x] the eligibility result exists and is linked to the same opportunity
  - [x] downstream planning steps still execute when eligibility is `ELIGIBLE`
  - [x] no duplicate eligibility records are created for the same deterministic path

## 1.3 Blocked eligibility stop behavior

- [x] Add integration test: eligibility `BLOCKED` stops the mission before TOS/legal, budget, wallet, submission packaging, email, and review execution.
- [x] Add integration test: multiple blocking reasons remain durable and deterministic in the integrated workflow trail.
- [x] Assert:
  - [x] the eligibility ledger record exists
  - [x] the stop point is visible in the mission timeline or audit trail
  - [x] no downstream budget, spend, rendered artifact, or experiment review record is created
  - [x] already-created scouting/source evidence remains archived

## 1.4 Incomplete and review-required behavior

- [x] Add integration test: eligibility `INCOMPLETE` stops autonomous progression and records the missing fields/reasons.
- [x] Add integration test: eligibility `NEEDS_REVIEW` stops autonomous progression and records the review-required reasons.
- [x] Assert:
  - [x] the exact integrated decision is preserved
  - [x] the exact reason codes are durable in the ledger payload
  - [x] no hidden fallback path bypasses the eligibility stop
  - [x] later workflow records are absent

## 1.5 Cross-check against execution-adjacent skills

- [x] Add integration assertion set proving blocked or incomplete eligibility cannot still produce:
  - [x] a budget plan
  - [x] a spend request
  - [x] an outbound email draft/send
  - [x] a submission package
  - [x] a rendered artifact

---

# 2. P0 - Add Rules-Change Recheck Workflow Coverage

## 2.1 Goal

Exercise the path where a mission already has prior rules context or a prior plan, then a later rules snapshot triggers `terms_change_monitor` and forces safe rechecks.

Primary files likely involved:

```text
tests/integration/test_new_skills_integration.py
tests/integration/test_plugin_phase_a_integration.py
src/openclaw_moneybot/skills/terms_change_monitor/
src/openclaw_moneybot/plugins/rules_snapshot_gateway/
src/openclaw_moneybot/orchestration/workflow.py
```

## 2.2 Prior-snapshot + no-change baseline

- [x] Add integration test: prior snapshot plus equivalent current snapshot yields a no-material-change result.
- [x] Assert:
  - [x] terms-change record is written
  - [x] severity is the expected no-change path
  - [x] no unnecessary budget or policy recheck requirement is set

## 2.3 Budget recheck path

- [x] Add integration test: changed payout amount or deadline triggers `requires_budget_recheck`.
- [x] Add integration test: previously approved planning context is not silently reused after the monitored change.
- [x] Assert:
  - [x] the terms-change record links back to the opportunity and evidence inputs
  - [x] the budget recheck flag is durable
  - [x] downstream execution remains blocked until refreshed planning exists

## 2.4 Policy recheck / block path

- [x] Add integration test: newly introduced automation prohibition or KYC/tax requirement triggers `requires_policy_recheck`.
- [x] Add integration test: highest-severity blocking phrase path stops execution even if prior planning artifacts already exist.
- [x] Assert:
  - [x] policy recheck requirement is durable and exact
  - [x] prior approval does not bypass the new block
  - [x] no spend/send/package execution happens after the changed rules are detected

## 2.5 Evidence and linkage expectations

- [x] Assert in all rules-change cases:
  - [x] prior and current evidence IDs are linked into the terms-change output
  - [x] the diff report evidence is archived
  - [x] the workflow leaves an auditable reason for the stop or recheck requirement

---

# 3. P0 - Add Submission Package -> Render -> Archive Integration Coverage

## 3.1 Goal

Cover the real handoff from submission preparation into rendered deliverables, evidence archival, and durable ledger state.

Primary files likely involved:

```text
tests/integration/test_new_skills_integration.py
tests/integration/test_plugin_phase_b_integration.py
src/openclaw_moneybot/skills/submission_package_builder/
src/openclaw_moneybot/plugins/artifact_renderer_plugin/
src/openclaw_moneybot/skills/receipt_and_evidence_archiver/
```

## 3.2 Package-build baseline

- [x] Add integration test: `submission_package_builder` produces a deterministic package for an eligible/approved opportunity.
- [x] Assert:
  - [x] package-related ledger records exist
  - [x] package evidence is archived
  - [x] the package references the correct opportunity, rules context, and supporting evidence

## 3.3 Builder -> renderer handoff

- [x] Add integration test: package output feeds `artifact_renderer_plugin` successfully using approved template inputs only.
- [x] Add integration test: renderer manifest and rendered content are linked back to the originating package or opportunity context.
- [x] Assert:
  - [x] rendered artifact ledger record exists
  - [x] manifest evidence and rendered-body evidence are archived
  - [x] content checksums and paths are deterministic
  - [x] no path escapes or unsafe template usage occur in the integrated path

## 3.4 Fail-closed handoff behavior

- [x] Add integration test: malformed or incomplete package data prevents rendering and fails closed.
- [x] Add integration test: unknown evidence reference in the rendering request is rejected before any false success artifact is created.
- [x] Assert:
  - [x] rejection reason is explicit
  - [x] no rendered artifact record exists on failure
  - [x] no misleading archive entry is created for a failed render

## 3.5 End-to-end traceability

- [x] Add integration assertion set proving one prepared package leaves a traceable chain across:
  - [x] package record
  - [x] rendered artifact record
  - [x] archive entries
  - [x] related audit events

---

# 4. P1 - Add Quarantine-to-Evidence Promotion Integration Coverage

## 4.1 Goal

Prove untrusted files and attachments only become downstream evidence through the bounded quarantine promotion path.

Primary files likely involved:

```text
tests/integration/test_plugin_phase_b_integration.py
tests/integration/test_plugin_phase_a_integration.py
src/openclaw_moneybot/plugins/download_quarantine_plugin/
src/openclaw_moneybot/plugins/inbox_observer_plugin/
src/openclaw_moneybot/skills/receipt_and_evidence_archiver/
```

## 4.2 Download ingest -> promotion path

- [x] Add integration test: safe downloaded file is ingested into quarantine, then promoted into the evidence archive.
- [x] Assert:
  - [x] quarantine scan record exists
  - [x] metadata status changes from staged to promoted
  - [x] promoted evidence record exists and points at the archived file
  - [x] content hash identity remains stable across staging and promotion

## 4.3 Inbox attachment -> quarantine -> promotion path

- [x] Add integration test: supported inbound attachment is observed, staged in quarantine, then promoted for downstream use.
- [x] Assert:
  - [x] inbox observation record exists
  - [x] attachment action and quarantine result are consistent
  - [x] promoted evidence can be referenced by a later package/render step

## 4.4 Rejection and boundary cases

- [x] Add integration test: rejected quarantine item cannot be promoted and cannot be used as downstream evidence.
- [x] Add integration test: unsupported attachment or download remains quarantined/rejected without false promotion metadata.
- [x] Assert:
  - [x] explicit rejection reasons are durable
  - [x] no downstream package/render/archive success path consumes the rejected file

---

# 5. P1 - Add Payout Reconciliation Loop Integration Coverage

## 5.1 Goal

Exercise the flow where observed payout state becomes deterministic reconciliation output and follow-up planning artifacts.

Primary files likely involved:

```text
tests/integration/test_new_skills_integration.py
tests/integration/test_plugin_phase_a_integration.py
src/openclaw_moneybot/plugins/wallet_observer_plugin/
src/openclaw_moneybot/skills/revenue_reconciler/
src/openclaw_moneybot/skills/payout_followup_planner/
```

## 5.2 Observed payout -> reconciled happy path

- [x] Add integration test: wallet observer records an inbound or outbound payment event, and `revenue_reconciler` matches it to the expected experiment or opportunity context.
- [x] Assert:
  - [x] wallet observation record exists
  - [x] reconciliation record exists
  - [x] matched transaction metadata is preserved
  - [x] resulting ROI/revenue fields are consistent with ledger history

## 5.3 Missing or partial payout path

- [x] Add integration test: expected payout is still missing and `payout_followup_planner` produces the correct bounded follow-up plan.
- [x] Add integration test: partial/ambiguous payment state yields the expected non-success reconciliation status.
- [x] Assert:
  - [x] follow-up plan record exists only when needed
  - [x] reasons and next steps are durable and deterministic
  - [x] no success-shaped reconciliation is produced for ambiguous payment state

## 5.4 Linkage and sequence checks

- [x] Add integration assertion set proving the payout loop links:
  - [x] opportunity or experiment context
  - [x] wallet observation
  - [x] reconciliation output
  - [x] follow-up planning output
  - [x] any evidence or notes emitted along the way

---

# 6. P1 - Add Counterparty Due-Diligence Integration Coverage

## 6.1 Goal

Cover the cross-boundary path from public counterparty capture into risk profiling and downstream planning/review state.

Primary files likely involved:

```text
tests/integration/test_plugin_phase_c_integration.py
tests/integration/test_new_skills_integration.py
src/openclaw_moneybot/plugins/counterparty_snapshot_plugin/
src/openclaw_moneybot/skills/counterparty_risk_profiler/
src/openclaw_moneybot/skills/budget_and_roi_planner/
```

## 6.2 Snapshot -> risk-profile baseline

- [x] Add integration test: public counterparty snapshot feeds `counterparty_risk_profiler` successfully.
- [x] Assert:
  - [x] snapshot record exists
  - [x] snapshot evidence is archived
  - [x] risk profile record exists and references the snapshot context

## 6.3 Changed or weak evidence path

- [x] Add integration test: weak or incomplete counterparty evidence produces the expected higher-risk profile or review-required state.
- [x] Add integration test: changed indicators between snapshots are visible in the resulting risk reasoning.
- [x] Assert:
  - [x] changed fields are durable
  - [x] evidence tier/freshness affect the integrated risk output as intended
  - [x] downstream planning or review reflects the elevated uncertainty

## 6.4 Downstream effect checks

- [x] Add integration test: counterparty risk output influences later planning or review records in a traceable way.
- [x] Assert:
  - [x] downstream record references the correct counterparty profile
  - [x] no unrelated opportunity or snapshot leaks into the decision path

---

# 7. P2 - Add Metrics Export Integration Coverage Against Real History

## 7.1 Goal

Generate exports from realistic ledger history built by multiple skills/plugins rather than isolated unit-test event fixtures.

Primary files likely involved:

```text
tests/integration/test_plugin_phase_c_integration.py
src/openclaw_moneybot/plugins/metrics_export_plugin/
src/openclaw_moneybot/skills/ledger_skill/
```

## 7.2 Experiment review export integration

- [x] Add integration test: create a realistic experiment lifecycle, then export experiment reviews as JSON and CSV.
- [x] Assert:
  - [x] exported rows match the underlying integrated ledger history
  - [x] output files are written under the approved export root
  - [x] export evidence/ledger metadata is recorded

## 7.3 Payout reconciliation export integration

- [x] Add integration test: build realistic reconciliation records and export payout reconciliation metrics.
- [x] Assert:
  - [x] status filtering works against real integrated records
  - [x] summary counts are deterministic
  - [x] missing optional typed records do not break export generation

## 7.4 Strategy summary export integration

- [x] Add integration test: build realistic strategy-summary records and export them with category filtering.
- [x] Assert:
  - [x] what-worked / what-failed counts match the integrated inputs
  - [x] malformed or unrelated ledger history is ignored safely

---

# 8. P2 - Add Replay and Idempotency Integration Coverage for New Paths

## 8.1 Goal

Prove that repeated execution of the newer packaging, reconciliation, monitoring, and export flows does not create inconsistent durable state.

Primary files likely involved:

```text
tests/integration/test_new_skills_integration.py
tests/integration/test_plugin_phase_b_integration.py
tests/integration/test_plugin_phase_c_integration.py
```

## 8.2 Packaging and rendering replay

- [x] Add integration test: replay the same submission-package and render request and verify no inconsistent duplicate durable records are created.
- [x] Assert:
  - [x] repeated outputs are either reused or remain deterministic
  - [x] archive and ledger linkage stays stable

## 8.3 Terms-change and reconciliation replay

- [x] Add integration test: replay the same terms-change evaluation and payout reconciliation request.
- [x] Assert:
  - [x] deterministic results are preserved
  - [x] duplicate or contradictory records are not created

## 8.4 Metrics export replay

- [x] Add integration test: run the same bounded export request twice and verify stable output content and durable metadata behavior.
- [x] Assert:
  - [x] no unsafe path drift occurs
  - [x] output naming/content rules remain deterministic

---

# 9. Shared integration-test infrastructure follow-ups

## 9.1 Scenario builders and helpers

- [x] Add or refine shared integration helpers for:
  - [x] creating realistic opportunities with linked rule snapshots
  - [x] building deterministic operator profiles for eligibility tests
  - [x] creating reusable evidence and archive fixtures for package/render flows
  - [x] seeding wallet observations, reconciliation inputs, and strategy summaries
  - [x] building realistic mixed ledger histories for metrics export

## 9.2 Quality and safety rules

- [x] Keep all new integration tests offline, local-only, and deterministic.
- [x] Avoid any live browser, live email, or live Bitcoin Core dependency.
- [x] Assert exact durable records and linkage where policy or audit behavior matters.
- [x] Prefer realistic local service boundaries over transport shims when the wrapper boundary is the thing being tested.
- [x] Reuse existing integration helpers where possible instead of duplicating setup logic.

---

# 10. Final validation and completion criteria

## 10.1 Validation tasks

- [x] Run `uv run --python 3.11 ruff check .`
- [x] Run `uv run --python 3.11 mypy .`
- [x] Run `uv run --python 3.11 pytest`
- [x] Confirm the new integration tests stay offline and deterministic under repeated local runs.

## 10.2 Acceptance criteria

- [x] Eligibility decisions are covered at the integrated workflow boundary, including safe stop behavior.
- [x] Rules-change monitoring is covered with durable budget/policy recheck propagation.
- [x] Submission packaging, rendering, archive, and ledger linkage are covered in one realistic flow.
- [x] Quarantine promotion is covered as the only safe path into downstream evidence use.
- [x] Payout observation, reconciliation, and follow-up planning are covered in one realistic flow.
- [x] Counterparty snapshot and risk profiling are covered as an integrated due-diligence path.
- [x] Metrics export is covered against realistic mixed ledger history rather than isolated fixtures only.
- [x] Replay/idempotency is covered for the new integration paths where duplicate durable state would be risky.
