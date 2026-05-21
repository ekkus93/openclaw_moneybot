# SKILLS1_TODO.md

# OpenClaw MoneyBot - New Skills Implementation TODO

This TODO tracks a first-party expansion pass for **new MoneyBot skills** that improve opportunity quality, execution readiness, payout tracking, and long-term learning **without** introducing unsafe autonomy or third-party plugin dependence.

The goal is **not** to add broad “do anything” agents. The goal is to add **narrow, separately testable skills** that:

- improve experiment selection quality
- reduce wasted work on ineligible or low-quality opportunities
- improve submission and payout follow-through
- preserve bounded autonomy, auditability, and fail-closed behavior
- keep dangerous authority behind existing governors and services

These skills should remain aligned with the current architecture:

```text
local LLM -> orchestration -> narrow skills -> deterministic validators/schemas
-> governed services -> local ledger/archive/wallet/email
```

---

# Priority legend

```text
P0 = highest-value risk/ROI improvements that directly prevent wasted work or missed payouts
P1 = important execution-quality and planning improvements
P2 = review, follow-up, and learning enhancements
```

---

# 0. Global rules for all new skills

- [x] Keep every new skill **narrow** and separately testable.
- [x] Do not create a broad multi-purpose “business operator” skill.
- [x] Do not add direct wallet, email-send, or browser-submit authority to any new skill.
- [x] Keep ledger writes behind `ledger_skill` or an equivalent narrow ledger API only.
- [x] Keep evidence storage behind `receipt_and_evidence_archiver` only.
- [x] Fail closed on missing prerequisites, malformed inputs, ambiguous rules, or unverifiable external state.
- [x] Require explicit typed request/response models for every new skill.
- [x] Add deterministic validators for safety-critical logic instead of relying on prompt-following alone.
- [x] Add unit tests for happy paths, blocked paths, and malformed-input paths.
- [x] Add integration tests where a new skill changes orchestration, review, or ledger linkage.
- [x] Keep new skills offline-friendly where possible.
- [x] Do not install third-party plugins or remotely hosted skills.
- [x] Prefer local files, local snapshots, local ledger queries, and local deterministic scoring.

---

# 1. Shared foundation work for new skills

## 1.1 Skill selection and sequencing

- [x] Confirm the initial implementation order for this new skill wave.
- [x] Recommended order:
  - [x] `account_eligibility_checker`
  - [x] `terms_change_monitor`
  - [x] `submission_package_builder`
  - [x] `revenue_reconciler`
  - [x] `counterparty_risk_profiler`
  - [x] `duplicate_opportunity_detector`
  - [x] `timebox_and_queue_planner`
  - [x] `deliverable_quality_checker`
  - [x] `payout_followup_planner`
  - [x] `strategy_memory_summarizer`
- [x] Decide which of these should be required in the default workflow versus optional support skills.

## 1.2 Shared contract and enum updates

- [x] Add or confirm shared enums/types needed by the new skills.
  - [x] eligibility decision enum
  - [x] terms-change severity enum
  - [x] submission readiness enum
  - [x] reconciliation status enum
  - [x] counterparty risk tier enum
  - [x] duplicate confidence enum
  - [x] queue priority enum
  - [x] deliverable validation outcome enum
  - [x] payout follow-up recommendation enum
  - [x] strategy lesson category enum
- [x] Add shared IDs/record link conventions for new skill outputs.
- [x] Ensure every new contract is serializable, stable, and suitable for ledger storage.

## 1.3 Ledger and evidence schema preparation

- [x] Decide whether new dedicated ledger record types are needed or whether existing generic records are sufficient.
- [x] If new record types are needed, add them safely.
  - [x] account eligibility records
  - [x] terms diff/change review records
  - [x] submission package records
  - [x] payout reconciliation records
  - [x] counterparty profile records
  - [x] duplicate-detection records
  - [x] queue/planning records
  - [x] deliverable quality check records
  - [x] follow-up plan records
  - [x] strategy memory summary records
- [x] Define which evidence artifacts each skill should archive.
- [x] Add or confirm evidence types for:
  - [x] eligibility snapshots
  - [x] terms diff reports
  - [x] submission checklists
  - [x] payout reconciliation snapshots
  - [x] counterparty profile snapshots
  - [x] duplicate opportunity comparison snapshots
  - [x] queue planning snapshots
  - [x] deliverable manifests
  - [x] payout follow-up drafts
  - [x] strategy summary snapshots

## 1.4 Orchestration planning

- [x] Decide where each skill plugs into the default workflow.
- [x] Add a high-level workflow map for the new skills.
  - [x] scouting -> eligibility -> policy/TOS -> budget
  - [x] budget -> submission package -> execution
  - [x] execution -> deliverable quality check -> evidence archive
  - [x] payout expected -> revenue reconciliation -> experiment review
  - [x] experiment review -> strategy memory summarizer
- [x] Define fail-closed stop points for each new handoff.

---

# 2. P0 - Implement `account_eligibility_checker`

## 2.1 Goal

Reject or flag opportunities that MoneyBot is **not actually eligible** to pursue before time or money is spent.

## 2.2 Required inputs

- [x] opportunity metadata
- [x] source/rules snapshots
- [x] policy and TOS/legal outputs where available
- [x] local operator capability/profile data that is explicitly allowed to be modeled
- [x] experiment constraints such as time, tools, repo requirements, payout method, and region

## 2.3 Required outputs

- [x] typed result model
  - [x] `decision`
  - [x] `confidence`
  - [x] `reasons`
  - [x] `missing_requirements`
  - [x] `blocked_requirements`
  - [x] `review_required_requirements`
  - [x] `safe_next_steps`
  - [x] `evidence_archive_ids`

## 2.4 Deterministic checks

- [x] Add checks for identity/account requirements.
  - [x] requires personal account
  - [x] requires non-bot social identity
  - [x] requires prior platform account age
  - [x] requires profile reputation/history
- [x] Add checks for legal/geo/operator constraints.
  - [x] geo restriction
  - [x] age restriction
  - [x] citizenship/residency restriction
  - [x] business entity requirement
  - [x] tax/KYC requirement
- [x] Add checks for technical/operational requirements.
  - [x] hardware requirement
  - [x] OS/software requirement
  - [x] private infrastructure requirement
  - [x] repository history requirement
  - [x] prior contribution requirement
- [x] Add checks for payout requirements.
  - [x] unsupported payout method
  - [x] unsupported currency/asset
  - [x] manual payment approval needed

## 2.5 Decision logic

- [x] Return `eligible` only when required criteria are positively satisfied.
- [x] Return `blocked` when required criteria are incompatible with MoneyBot constraints.
- [x] Return `needs_review` when requirements are ambiguous or unverifiable.
- [x] Return `incomplete` when key eligibility data is missing.

## 2.6 Ledger/evidence integration

- [x] Record the eligibility decision durably.
- [x] Archive the rules snippets or structured evidence that supported the decision.
- [x] Link the decision to the opportunity and later budget/review records.

## 2.7 Unit tests

- [x] Eligible low-risk opportunity passes.
- [x] Personal-account requirement blocks.
- [x] Geo restriction blocks.
- [x] Unsupported payout method blocks.
- [x] Ambiguous eligibility requirement becomes `needs_review`.
- [x] Missing rule text becomes `incomplete`.
- [x] Evidence linkage is preserved.

## 2.8 Integration tests

- [x] Workflow stops before budget/execution when eligibility is blocked.
- [x] Workflow stops safely when eligibility is `needs_review`.

---

# 3. P0 - Implement `terms_change_monitor`

## 3.1 Goal

Detect meaningful changes in opportunity rules or payout terms and prevent stale approvals from being reused blindly.

## 3.2 Required inputs

- [x] prior archived rules/terms snapshots
- [x] newly captured rules/terms snapshots
- [x] related opportunity identifiers
- [x] prior TOS/legal and budget outputs where available

## 3.3 Required outputs

- [x] typed diff result model
  - [x] `change_detected`
  - [x] `severity`
  - [x] `changed_fields`
  - [x] `summary`
  - [x] `requires_recheck`
  - [x] `requires_budget_recheck`
  - [x] `requires_policy_recheck`
  - [x] `evidence_archive_ids`

## 3.4 Diff categories

- [x] eligibility changes
- [x] payout amount changes
- [x] payout method changes
- [x] submission deadline changes
- [x] automation/bot policy changes
- [x] KYC/tax requirement changes
- [x] required deliverable changes
- [x] dispute/refund/chargeback language changes

## 3.5 Severity rules

- [x] `none` for formatting-only or irrelevant changes
- [x] `low` for non-execution-impacting informational changes
- [x] `medium` for changes requiring review or refreshed evidence
- [x] `high` for changes that invalidate previous approval/budget assumptions
- [x] `block` for changes that newly prohibit automation or invalidate safe execution

## 3.6 Recheck hooks

- [x] Trigger TOS/legal recheck when rules meaningfully changed.
- [x] Trigger budget recheck when costs, payout, or deadlines changed.
- [x] Trigger policy recheck when prohibited categories or higher-risk actions appear.
- [x] Invalidate stale execution packages when required.

## 3.7 Ledger/evidence integration

- [x] Store diff summary and impacted fields.
- [x] Archive before/after snapshots and diff output.
- [x] Link diff records to the opportunity timeline.

## 3.8 Unit tests

- [x] No-op formatting change stays low severity.
- [x] Payout reduction triggers budget recheck.
- [x] Bot prohibition triggers block severity.
- [x] Deadline change triggers review.
- [x] Missing old snapshot fails closed.

## 3.9 Integration tests

- [x] Existing approved opportunity gets stopped when monitored terms newly block automation.
- [x] Existing approved budget is invalidated when payout or fee assumptions materially change.

---

# 4. P0 - Implement `submission_package_builder`

## 4.1 Goal

Turn an approved opportunity into a concrete, traceable submission package so execution is bounded and complete.

## 4.2 Required inputs

- [x] opportunity data
- [x] policy decision
- [x] TOS/legal output
- [x] budget plan
- [x] archived rules/source evidence
- [x] operator-provided mission context where allowed

## 4.3 Required outputs

- [x] typed submission package model
  - [x] `submission_package_id`
  - [x] `status`
  - [x] `required_steps`
  - [x] `required_fields`
  - [x] `required_artifacts`
  - [x] `required_evidence`
  - [x] `submission_url`
  - [x] `deadline`
  - [x] `quality_checks`
  - [x] `handoff_notes`
  - [x] `evidence_archive_ids`

## 4.4 Required logic

- [x] Extract required deliverables from rules.
- [x] Extract required form fields.
- [x] Extract required attachments/screenshots/proof.
- [x] Extract any submission deadlines or sequencing rules.
- [x] Normalize the package into a deterministic checklist.
- [x] Mark unclear items as review-required instead of guessing.

## 4.5 Safety constraints

- [x] Do not auto-submit.
- [x] Do not invent missing submission fields.
- [x] Do not fabricate claims or deliverables.
- [x] Do not proceed if required inputs are missing or ambiguous.

## 4.6 Ledger/evidence integration

- [x] Record submission package in the ledger.
- [x] Archive package snapshot and source extraction evidence.
- [x] Link package to budget, opportunity, and later submission evidence.

## 4.7 Unit tests

- [x] Structured rules become deterministic checklist items.
- [x] Missing required field text becomes review-required.
- [x] Conflicting deliverable instructions fail closed.
- [x] Submission URL and deadline are preserved.

## 4.8 Integration tests

- [x] Approved workflow can produce a submission package before execution.
- [x] Execution stops when package has unresolved required items.

---

# 5. P0 - Implement `revenue_reconciler`

## 5.1 Goal

Compare expected payouts against actual wallet receipts, email confirmations, and archived proof so MoneyBot can track revenue accurately.

## 5.2 Required inputs

- [x] experiment/opportunity identifiers
- [x] expected payout data from plan/review
- [x] wallet transaction or payment-observer data
- [x] archived receipts/invoices/emails
- [x] manual payout metadata where applicable

## 5.3 Required outputs

- [x] typed reconciliation result model
  - [x] `status`
  - [x] `expected_amount`
  - [x] `observed_amount`
  - [x] `currency_or_asset`
  - [x] `variance`
  - [x] `matched_artifacts`
  - [x] `missing_artifacts`
  - [x] `followup_recommended`
  - [x] `reason_codes`
  - [x] `evidence_archive_ids`

## 5.4 Deterministic matching logic

- [x] Match by experiment/opportunity identifiers.
- [x] Match by date window.
- [x] Match by amount tolerance.
- [x] Match by counterparty/platform.
- [x] Match by txid/reference/message id where available.
- [x] Refuse to over-match ambiguous receipts.

## 5.5 Reconciliation outcomes

- [x] `matched`
- [x] `partial`
- [x] `missing`
- [x] `late`
- [x] `underpaid`
- [x] `overpaid_needs_review`
- [x] `ambiguous_needs_review`

## 5.6 Ledger/evidence integration

- [x] Store reconciliation records durably.
- [x] Link matched payout proof back to the experiment.
- [x] Surface unresolved payout issues to experiment review.

## 5.7 Unit tests

- [x] Exact payout match succeeds.
- [x] Underpayment is detected.
- [x] Missing payout becomes unresolved.
- [x] Ambiguous multiple receipts becomes review-required.
- [x] Late payout window is flagged.

## 5.8 Integration tests

- [x] Completed experiment with payout proof reconciles successfully.
- [x] Missing payout causes follow-up recommendation and review linkage.

---

# 6. P1 - Implement `counterparty_risk_profiler`

## 6.1 Goal

Score counterparties/platforms using deterministic, explainable signals before MoneyBot commits effort or spend.

## 6.2 Required inputs

- [x] platform/domain metadata
- [x] rules clarity indicators
- [x] payout history from prior experiments
- [x] dispute history from local records
- [x] support responsiveness observations
- [x] domain and identity hygiene signals available locally

## 6.3 Required outputs

- [x] typed profile result model
  - [x] `risk_tier`
  - [x] `score`
  - [x] `positive_signals`
  - [x] `negative_signals`
  - [x] `unknowns`
  - [x] `recommended_action`
  - [x] `evidence_archive_ids`

## 6.4 Scoring signals

- [x] clear payout rules
- [x] clear deadlines
- [x] historical payout success rate
- [x] prior disputes
- [x] inconsistent wording or suspicious claims
- [x] missing support channel
- [x] new or unstable domain
- [x] unexplained KYC or off-platform payment requirements

## 6.5 Decision logic

- [x] low-risk counterparties are allowed to proceed to normal workflow
- [x] medium-risk counterparties trigger caution/review notes
- [x] high-risk counterparties trigger `needs_review` or `block`

## 6.6 Unit tests

- [x] Positive history lowers risk.
- [x] Missing payout proof raises risk.
- [x] Suspicious off-platform payment request raises risk.
- [x] Unknown data does not silently produce low risk.

## 6.7 Integration tests

- [x] High-risk profile feeds into planning/review and blocks autonomous continuation where configured.

---

# 7. P1 - Implement `duplicate_opportunity_detector`

## 7.1 Goal

Prevent duplicate work across reposted or substantially identical opportunities.

## 7.2 Required inputs

- [x] candidate opportunity data
- [x] prior opportunity ledger records
- [x] title, URL, description, payout, rules URL, and platform metadata

## 7.3 Required outputs

- [x] typed duplicate result model
  - [x] `is_duplicate`
  - [x] `confidence`
  - [x] `matched_opportunity_ids`
  - [x] `match_reasons`
  - [x] `safe_next_steps`

## 7.4 Matching logic

- [x] exact URL match
- [x] normalized rules URL match
- [x] normalized title match
- [x] high textual similarity with same platform/payout/deadline
- [x] near-duplicate detection for reposts with minor edits
- [x] fail closed when duplicate evidence is strong

## 7.5 Unit tests

- [x] Exact repost is detected.
- [x] Same content with small title variation is detected.
- [x] Different opportunity with similar wording is not over-blocked.
- [x] Missing metadata degrades to review, not false uniqueness.

## 7.6 Integration tests

- [x] Scout/orchestration path avoids creating duplicate active opportunities where configured.

---

# 8. P1 - Implement `timebox_and_queue_planner`

## 8.1 Goal

Prioritize bounded experiments by ROI, deadline, uncertainty, and current capacity.

## 8.2 Required inputs

- [x] approved or candidate opportunities
- [x] budget plans
- [x] current time/capacity constraints
- [x] open experiments
- [x] deadlines and payout timing
- [x] risk/review flags

## 8.3 Required outputs

- [x] typed queue/plan result model
  - [x] `items`
  - [x] `priority`
  - [x] `timebox_hours`
  - [x] `budget_reservation`
  - [x] `queue_reason`
  - [x] `defer_reason`

## 8.4 Planning logic

- [x] prioritize high expected value with low downside
- [x] deprioritize ambiguous or review-blocked items
- [x] account for deadlines
- [x] account for daily/weekly budget headroom
- [x] cap the number of concurrent active experiments
- [x] avoid requeue loops for repeatedly failing experiments

## 8.5 Unit tests

- [x] High ROI + near deadline ranks first.
- [x] Review-blocked item is deferred.
- [x] Budget-constrained item is deferred safely.
- [x] Repeated loser gets deprioritized.

## 8.6 Integration tests

- [x] Queue planning output can drive orchestrator selection order without bypassing policy/budget gates.

---

# 9. P1 - Implement `deliverable_quality_checker`

## 9.1 Goal

Verify that all required deliverables and submission evidence are present before submission or review completion.

## 9.2 Required inputs

- [x] submission package
- [x] archived deliverables
- [x] archived screenshots/html snapshots
- [x] expected metadata and artifact list

## 9.3 Required outputs

- [x] typed quality result model
  - [x] `status`
  - [x] `missing_items`
  - [x] `invalid_items`
  - [x] `warnings`
  - [x] `passed_checks`
  - [x] `evidence_archive_ids`

## 9.4 Checks

- [x] required files exist
- [x] required screenshots exist
- [x] hashes match expected archived artifacts where applicable
- [x] required fields are non-empty
- [x] deliverable count matches rules
- [x] forbidden placeholder text is absent
- [x] generated output references the right opportunity/experiment IDs

## 9.5 Unit tests

- [x] Complete package passes.
- [x] Missing screenshot fails.
- [x] Placeholder content fails.
- [x] Hash mismatch fails.
- [x] Optional warning does not become false success for required fields.

## 9.6 Integration tests

- [x] Submission/execution path halts when deliverable quality check fails.

---

# 10. P2 - Implement `payout_followup_planner`

## 10.1 Goal

Recommend safe follow-up actions when a payout is late, missing, partial, or disputed.

## 10.2 Required inputs

- [x] reconciliation results
- [x] experiment review data
- [x] archived receipts/emails/terms
- [x] counterparty profile

## 10.3 Required outputs

- [x] typed follow-up plan model
  - [x] `recommendation`
  - [x] `draft_needed`
  - [x] `suggested_message_purpose`
  - [x] `required_supporting_evidence`
  - [x] `timing_recommendation`
  - [x] `stop_conditions`

## 10.4 Allowed recommendations

- [x] wait
- [x] gather_missing_proof
- [x] draft_followup
- [x] human_review
- [x] stop_and_record_loss

## 10.5 Constraints

- [x] Do not automatically send follow-up messages.
- [x] Do not escalate beyond safe bounded recommendations.
- [x] Require supporting evidence before recommending outreach.
- [x] Fail closed when payout terms are ambiguous.

## 10.6 Unit tests

- [x] Late but still inside grace period recommends wait.
- [x] Missing proof recommends gather evidence first.
- [x] Underpaid with clear evidence recommends draft follow-up.
- [x] High-risk counterparty recommends human review.

## 10.7 Integration tests

- [x] Reconciliation output can feed into follow-up planning and experiment review without unsafe auto-send behavior.

---

# 11. P2 - Implement `strategy_memory_summarizer`

## 11.1 Goal

Convert experiment outcomes into reusable structured lessons that improve future scouting, budgeting, and risk decisions.

## 11.2 Required inputs

- [x] experiment reviews
- [x] budget outcomes
- [x] payout reconciliation results
- [x] counterparty outcomes
- [x] time spent and ROI data

## 11.3 Required outputs

- [x] typed strategy summary model
  - [x] `summary_id`
  - [x] `scope`
  - [x] `lesson_categories`
  - [x] `what_worked`
  - [x] `what_failed`
  - [x] `heuristics_to_keep`
  - [x] `heuristics_to_avoid`
  - [x] `evidence_archive_ids`

## 11.4 Summarization constraints

- [x] Keep summaries grounded in ledgered facts, not speculation.
- [x] Separate hard lessons from tentative hypotheses.
- [x] Avoid overwriting historical context silently.
- [x] Prefer structured fields over prose-only memory.

## 11.5 Consumers

- [x] opportunity scouting heuristics
- [x] budget planning heuristics
- [x] counterparty risk profiling
- [x] queue prioritization

## 11.6 Unit tests

- [x] Successful recurring pattern becomes reusable heuristic.
- [x] One-off noisy incident does not become an overgeneralized rule.
- [x] Contradictory results become tentative, not hard-coded.

## 11.7 Integration tests

- [x] Completed review/reconciliation pipeline can emit a strategy summary linked to the experiment.

---

# 12. Cross-cutting implementation tasks

## 12.1 Directory and package layout

- [x] Create skill packages and `SKILL.md` files for each new skill.
- [x] Use the existing repository conventions for:
  - [x] `models.py`
  - [x] `runner.py`
  - [x] `SKILL.md`
  - [x] unit tests
  - [x] integration tests where needed

## 12.2 Documentation

- [x] Add a `SKILL.md` for each new skill with:
  - [x] purpose
  - [x] inputs
  - [x] outputs
  - [x] fail-closed behavior
  - [x] examples
  - [x] non-goals
- [x] Update top-level docs if default workflow changes.
- [x] Update `docs/TODO.md` if these skills become part of the main roadmap.

## 12.3 Test fixtures and helpers

- [x] Add reusable fixtures for:
  - [x] eligibility rule scenarios
  - [x] old/new terms snapshots
  - [x] submission package scenarios
  - [x] payout reconciliation scenarios
  - [x] duplicate opportunity datasets
  - [x] queue planning datasets
  - [x] deliverable manifests
  - [x] experiment review outcome bundles

## 12.4 Review and acceptance pass

- [x] Run `uv run --python 3.11 ruff check .`
- [x] Run `uv run --python 3.11 mypy .`
- [x] Run `uv run --python 3.11 pytest`
- [x] Add focused regression tests for any safety-sensitive bug found during implementation.
- [x] Confirm no new skill bypasses policy, budget, ledger, evidence, wallet, email, or browser governors.

---

# 13. Suggested implementation phases

## Phase A - Highest-value gating and payout skills

- [x] Implement `account_eligibility_checker`
- [x] Implement `terms_change_monitor`
- [x] Implement `submission_package_builder`
- [x] Implement `revenue_reconciler`

## Phase B - Planning and risk support skills

- [x] Implement `counterparty_risk_profiler`
- [x] Implement `duplicate_opportunity_detector`
- [x] Implement `timebox_and_queue_planner`
- [x] Implement `deliverable_quality_checker`

## Phase C - Review and learning support skills

- [x] Implement `payout_followup_planner`
- [x] Implement `strategy_memory_summarizer`

---

# 14. Final acceptance criteria

This TODO is complete when:

- [x] all selected new skills have narrow typed contracts
- [x] each skill has explicit fail-closed behavior
- [x] each skill has unit tests for success, blocked, and malformed-input paths
- [x] integration tests exist where workflow or durable-record behavior changed
- [x] no new skill has direct wallet-send, email-send, or browser-submit authority
- [x] ledger and evidence linkage is preserved for all meaningful outputs
- [x] default safety constraints remain intact
- [x] `ruff`, `mypy`, and `pytest` all pass

---

# 15. Final note

These skills should remain **first-party**, local, auditable, and constrained.

If any skill starts to look like a broad “operator agent,” split it back into narrower deterministic components before implementation.
