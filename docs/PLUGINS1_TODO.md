# PLUGINS1_TODO.md

# OpenClaw MoneyBot - New Plugins Implementation TODO

This TODO tracks a first-party expansion pass for **new MoneyBot plugins/services** that support the next skill wave without giving the LLM or orchestration layer unsafe direct authority.

The goal is **not** to install third-party plugins or create broad remote-control adapters. The goal is to add **narrow, deterministic, auditable local plugins** that:

- supply trusted local state to skills
- capture and normalize evidence safely
- improve reconciliation, deadlines, and follow-up handling
- reduce duplicate work and stale decisions
- preserve strict trust boundaries around money, messaging, browsing, and secrets

These plugins should remain aligned with the current architecture:

```text
local LLM -> orchestration -> narrow skills -> deterministic validators/schemas
-> governed plugins/services -> local ledger/archive/wallet/email
```

---

# Priority legend

```text
P0 = highest-value supporting plugins for safety, eligibility, and payout correctness
P1 = important execution-readiness and operational-efficiency plugins
P2 = analytics, indexing, and quality-of-life plugins
```

---

# 0. Global rules for all new plugins

- [ ] Keep every new plugin/service **narrow** and separately testable.
- [ ] Do not install third-party plugins, hosted agents, or externally managed services.
- [ ] Prefer local Python modules or localhost-only services over network-exposed components.
- [ ] Keep any HTTP service bound to `127.0.0.1` unless there is a documented reason not to.
- [ ] Do not give any new plugin direct wallet-send authority.
- [ ] Do not give any new plugin direct unrestricted email-send authority.
- [ ] Do not give any new plugin unrestricted browser automation or unrestricted shell access.
- [ ] Fail closed on malformed input, unsupported actions, missing configuration, ambiguous authority, or unverifiable external data.
- [ ] Require typed request/response models for every plugin boundary.
- [ ] Require deterministic validation for safety-critical behavior.
- [ ] Keep secrets out of prompts, logs, error payloads, and persisted evidence.
- [ ] Keep all durable writes linked through the ledger and evidence archive.
- [ ] Add unit tests for happy paths, blocked paths, and malformed-input paths.
- [ ] Add integration tests for every plugin that changes orchestration, ledger linkage, archive linkage, or local service boundaries.
- [ ] Prefer read-only adapters before adding any state-changing adapter.
- [ ] Use allowlists for filesystems, URLs, content types, and operations whenever a plugin touches external inputs.

---

# 1. Shared foundation work for the new plugin wave

## 1.1 Confirm plugin scope and sequencing

- [x] Confirm that this wave is limited to **first-party** plugins only.
- [x] Confirm the initial implementation order for the plugin wave.
- [ ] Recommended order:
  - [x] `operator_profile_store`
  - [x] `rules_snapshot_gateway`
  - [x] `wallet_observer_plugin`
  - [x] `inbox_observer_plugin`
  - [ ] `opportunity_index_plugin`
  - [ ] `artifact_renderer_plugin`
  - [ ] `deadline_scheduler_plugin`
  - [ ] `download_quarantine_plugin`
  - [ ] `counterparty_snapshot_plugin`
  - [ ] `metrics_export_plugin`
- [ ] Mark which plugins are required for the default workflow and which remain optional helpers.

## 1.2 Shared plugin conventions

- [x] Decide where each plugin should live in the repo structure.
  - [x] local Python module under `src/openclaw_moneybot/plugins/`
  - [ ] localhost-only service wrapper where process separation is desirable
- [x] Define standard plugin config loading patterns.
- [x] Define standard health-check behavior for service-style plugins.
- [ ] Define standard error model and error-code conventions for plugin failures.
- [ ] Define standard idempotency requirements for any plugin that persists state.
- [x] Define standard audit-event conventions for plugin reads, writes, and rejections.

## 1.3 Shared contracts and enums

- [x] Add or confirm shared enums/types needed by the new plugins.
  - [x] profile attribute availability enum
  - [x] snapshot freshness enum
  - [x] inbound message classification enum
  - [x] opportunity similarity enum
  - [x] artifact render outcome enum
  - [x] deadline state enum
  - [x] quarantine scan status enum
  - [x] counterparty evidence tier enum
  - [x] export job status enum
- [x] Add shared record-link conventions so plugin outputs can be tied to opportunities, experiments, reviews, and evidence.
- [x] Ensure every plugin contract is serializable and stable for ledger persistence.

## 1.4 Shared security controls

- [ ] Define path allowlists for every plugin that reads or writes files.
- [x] Define host/domain allowlists for every plugin that fetches remote content.
- [x] Define content-type allowlists for downloads and imported artifacts.
- [x] Define maximum payload/file sizes.
- [ ] Define per-plugin timeouts and retry rules.
- [ ] Define redaction rules for inbound content, account data, and receipts.
- [x] Decide which plugins must operate in read-only mode by default.

## 1.5 Shared ledger and evidence preparation

- [x] Decide whether new dedicated ledger record types are needed for plugin-originated events.
- [x] If needed, add safe record support for:
  - [x] operator profile snapshots
  - [x] rule snapshot captures
  - [x] wallet observation snapshots
  - [x] inbox observation events
  - [x] opportunity index records
  - [x] rendered artifact manifests
  - [x] deadline schedule events
  - [x] quarantine scan results
  - [x] counterparty snapshot records
  - [x] metrics export jobs
- [ ] Define which plugin outputs must be archived as evidence.
- [ ] Define retention expectations for snapshot-style plugin outputs.

## 1.6 Orchestration wiring plan

- [ ] Map each plugin to the skills that depend on it.
  - [ ] `account_eligibility_checker` -> `operator_profile_store`
  - [ ] `terms_change_monitor` -> `rules_snapshot_gateway`
  - [ ] `revenue_reconciler` -> `wallet_observer_plugin`
  - [ ] `payout_followup_planner` -> `inbox_observer_plugin`
  - [ ] `duplicate_opportunity_detector` -> `opportunity_index_plugin`
  - [ ] `submission_package_builder` -> `artifact_renderer_plugin`
  - [ ] `timebox_and_queue_planner` -> `deadline_scheduler_plugin`
  - [ ] `tos_legal_checker` and `submission_package_builder` -> `download_quarantine_plugin`
  - [ ] `counterparty_risk_profiler` -> `counterparty_snapshot_plugin`
  - [ ] `experiment_reviewer` and `strategy_memory_summarizer` -> `metrics_export_plugin`
- [ ] Define fail-closed workflow stop points when a required plugin is unavailable or returns stale/unsafe data.

---

# 2. P0 - Implement `operator_profile_store`

## 2.1 Goal

Provide a narrow local store of operator capabilities and allowed account/profile attributes so eligibility logic can use deterministic facts without exposing personal accounts or prompting the LLM to invent them.

## 2.2 Supported data

- [x] Allowed operator region metadata
- [x] allowed working hours or time-budget caps
- [x] allowed hardware/software capabilities
- [x] allowed payout methods
- [x] allowed legal/business status flags
- [x] approved repository/history capabilities
- [x] explicit deny flags for personal-account-only requirements

## 2.3 Hard boundaries

- [x] Do not store personal account credentials.
- [x] Do not store personal email credentials.
- [x] Do not store KYC documents, government IDs, or sensitive secrets.
- [x] Do not expose profile fields that the operator has not explicitly configured.
- [x] Return `unknown` rather than guessing.

## 2.4 Implementation tasks

- [x] Create plugin module and config models.
- [x] Define typed read/write request models.
- [x] Define allowed profile fields and validation rules.
- [x] Add support for explicit field provenance metadata.
- [x] Add support for profile versioning and last-updated timestamps.
- [x] Add read-only query helpers for eligibility checks.
- [x] Add audit events for profile creation and modification.
- [x] Add safe export/redaction behavior for diagnostics.

## 2.5 Tests

- [x] Reading configured profile data succeeds.
- [x] Unknown field access returns a safe structured result.
- [x] Unsupported field write is rejected.
- [x] Sensitive field types are rejected.
- [x] Provenance metadata is preserved.
- [x] Versioning and audit linkage are preserved.

## 2.6 Acceptance criteria

- [x] Eligibility skills can consume deterministic operator facts.
- [x] No secrets or personal-account credentials are exposed.
- [x] Missing data fails closed as `unknown` instead of assumed true.

---

# 3. P0 - Implement `rules_snapshot_gateway`

## 3.1 Goal

Capture, normalize, hash, and version rule/terms snapshots so stale approvals can be detected and legal/TOS checks can be tied to durable before/after evidence.

## 3.2 Supported responsibilities

- [x] Capture HTML/text snapshots from allowlisted opportunity rule sources.
- [x] Normalize line endings and strip clearly irrelevant noise where deterministic.
- [x] Store hash, capture timestamp, source URL, and content type.
- [x] Compare new snapshots against prior snapshots for the same opportunity/source.
- [x] Produce a stable diff artifact for downstream review.

## 3.3 Hard boundaries

- [x] Do not execute JavaScript in an unrestricted browser context.
- [x] Do not log raw secrets or session data from fetched pages.
- [x] Do not silently accept oversized or unsupported content types.
- [x] Do not fetch arbitrary domains without allowlist checks.

## 3.4 Implementation tasks

- [x] Create plugin module and config models.
- [x] Define allowlisted source configuration.
- [x] Define typed capture, fetch, and diff result models.
- [x] Add content-size and content-type enforcement.
- [x] Add normalization pipeline for deterministic snapshots.
- [x] Add hashing and snapshot identity logic.
- [x] Add previous-snapshot lookup helpers.
- [x] Add stable diff generation.
- [x] Archive raw and normalized snapshots through the evidence archive.
- [x] Record snapshot metadata and diff summaries in the ledger.

## 3.5 Tests

- [x] Initial snapshot capture succeeds.
- [x] Same-content recapture yields same hash identity expectations.
- [x] Meaningful text changes appear in diff output.
- [x] Unsupported content type is rejected.
- [x] Oversized content is rejected.
- [x] Non-allowlisted host is rejected.
- [x] Evidence and ledger linkage are preserved.

## 3.6 Acceptance criteria

- [x] Terms/TOS reviews can rely on durable versioned snapshots.
- [x] Snapshot changes are detectable and auditable.
- [x] Unsafe fetches fail closed.

---

# 4. P0 - Implement `wallet_observer_plugin`

## 4.1 Goal

Provide a read-only wallet observation layer that can support reconciliation and payout tracking without expanding spend authority.

## 4.2 Supported responsibilities

- [x] Read current wallet balance through approved local interfaces.
- [x] Read transaction summaries relevant to MoneyBot-recorded spends and receipts.
- [x] Normalize tx metadata for ledger comparison.
- [x] Detect confirmation-state changes for tracked transactions.
- [x] Surface read-only balance and transaction snapshots for reconciliation.

## 4.3 Hard boundaries

- [x] Do not broadcast transactions.
- [x] Do not unlock the wallet.
- [x] Do not expose wallet secrets, RPC cookies, or passphrases.
- [x] Do not expose arbitrary raw RPC capability.
- [x] Do not mutate wallet state.

## 4.4 Implementation tasks

- [x] Decide whether to integrate through `wallet_governor_service`, a dedicated read-only adapter, or both.
- [x] Define typed balance and transaction observation models.
- [x] Add tx lookup by recorded txid or ledger reference.
- [x] Add confirmation-status normalization.
- [x] Add mismatch detection against ledger-recorded amounts and fees.
- [x] Add read-only snapshot archival where helpful.
- [x] Add audit events for balance/tx observation failures.

## 4.5 Tests

- [x] Read-only balance fetch succeeds.
- [x] Transaction lookup succeeds for known txid.
- [x] Missing txid returns a safe structured result.
- [x] Mismatched amount/fee is surfaced deterministically.
- [x] Observation failures generate audit records.
- [x] No spend-capable path exists through the plugin API.

## 4.6 Acceptance criteria

- [x] Revenue reconciliation can inspect wallet state without spend authority.
- [x] Ledger and wallet mismatches are surfaced explicitly.
- [x] The plugin is provably read-only.

---

# 5. P0 - Implement `inbox_observer_plugin`

## 5.1 Goal

Provide a bounded, mostly read-only inbox observation layer so MoneyBot can track payout notices, responses, and follow-up state without granting unrestricted mail authority.

## 5.2 Supported responsibilities

- [x] Read inbound messages from a dedicated bot mailbox.
- [x] Normalize headers, sender, thread identifiers, timestamps, and safe body excerpts.
- [x] Classify common message types deterministically where possible.
  - [x] payout notice
  - [x] positive response
  - [x] rejection
  - [x] opt-out
  - [x] complaint
  - [x] unknown
- [x] Link messages to known opportunity, experiment, or thread IDs where possible.
- [x] Surface follow-up-relevant state to planning/review skills.

## 5.3 Hard boundaries

- [x] Do not read the operator's personal inbox.
- [x] Do not expose mailbox credentials to the LLM.
- [x] Do not auto-send mail.
- [x] Do not auto-reply.
- [x] Do not silently ingest unsupported attachment types.

## 5.4 Implementation tasks

- [x] Define config for the dedicated bot mailbox only.
- [x] Define typed inbound message, thread summary, and classification result models.
- [x] Add read-only inbox polling/fetch helpers.
- [x] Add thread-linking heuristics using message IDs and known references.
- [x] Add deterministic classification helpers for common reply categories.
- [x] Add evidence archival for headers, bodies, and safe attachment metadata.
- [x] Add quarantine handoff for attachments when needed.
- [x] Add audit events for fetch failures and parse failures.

## 5.5 Tests

- [x] Payout notice is classified correctly.
- [x] Opt-out message is classified correctly.
- [x] Complaint message is classified correctly.
- [x] Unknown message stays unknown.
- [x] Personal-mailbox config is rejected.
- [x] Unsupported attachment type is quarantined or rejected safely.
- [x] Thread linkage is preserved.

## 5.6 Acceptance criteria

- [x] Follow-up and reconciliation skills can consume inbound state safely.
- [x] No send capability is added.
- [x] Inbox evidence and audit records are durable and linkable.

---

# 6. P1 - Implement `opportunity_index_plugin`

## 6.1 Goal

Provide a local structured index for opportunities, rules snapshots, outcomes, and archived evidence so duplicate detection and strategy memory do not need to re-scan the entire ledger naively.

## 6.2 Supported responsibilities

- [x] Index opportunity titles, normalized URLs, counterparties, tags, reward ranges, and source hashes.
- [x] Index relevant rule hashes and snapshot IDs.
- [x] Index outcome labels and review summaries.
- [x] Provide deterministic duplicate and similarity queries.
- [x] Provide lightweight local search helpers for prior experiments.

## 6.3 Hard boundaries

- [x] Do not expose arbitrary full-database SQL.
- [x] Do not permit destructive reindex operations without explicit operator action.
- [x] Do not mix unrelated repositories or personal data sources.

## 6.4 Implementation tasks

- [x] Decide whether to implement as SQLite-side indexed tables, FTS-backed helpers, or a small local service facade.
- [x] Define typed index/update/query models.
- [x] Add normalized URL/counterparty/title canonicalization.
- [x] Add similarity scoring rules.
- [x] Add duplicate candidate explanation output.
- [x] Add incremental update hooks from ledger/evidence events.
- [x] Add safe rebuild tooling for local maintenance.

## 6.5 Tests

- [x] Similar opportunities are surfaced as duplicates.
- [x] Distinct opportunities are not over-merged.
- [x] Incremental indexing updates results correctly.
- [x] Unsafe query shapes are rejected.
- [x] Rebuild path preserves determinism.

## 6.6 Acceptance criteria

- [x] Duplicate-detection and strategy-memory skills have a fast, deterministic local backing index.
- [x] Query behavior is bounded and auditable.

---

# 7. P1 - Implement `artifact_renderer_plugin`

## 7.1 Goal

Deterministically assemble submission bundles, deliverable manifests, and proof packages from already-approved content and archived evidence.

## 7.2 Supported responsibilities

- [x] Render structured submission packages from approved templates and input data.
- [x] Produce deterministic file manifests and checksums.
- [x] Bundle references to evidence artifacts, deliverables, and metadata.
- [x] Validate required fields before rendering.
- [x] Produce a render report for review and archival.

## 7.3 Hard boundaries

- [x] Do not submit forms or send packages directly.
- [x] Do not fetch remote templates from untrusted sources.
- [x] Do not render files outside approved workspace paths.
- [x] Do not include secrets or rejected evidence artifacts.

## 7.4 Implementation tasks

- [x] Define approved local template format(s).
- [x] Define typed render request/result models.
- [x] Add required-field validation and placeholder validation.
- [x] Add deterministic file ordering and checksum generation.
- [x] Add manifest generation.
- [x] Add archive integration for rendered outputs and manifests.
- [x] Add ledger linkage for rendered submission bundles.

## 7.5 Tests

- [x] Valid render request produces expected package outputs.
- [x] Missing required fields are rejected.
- [x] Unknown template reference is rejected.
- [x] Out-of-bounds output path is rejected.
- [x] Manifest and checksums are stable across repeated renders.

## 7.6 Acceptance criteria

- [x] Submission and proof packages are deterministic, reviewable, and archived.
- [x] The plugin never performs the actual submission step.

---

# 8. P1 - Implement `deadline_scheduler_plugin`

## 8.1 Goal

Track opportunity deadlines, follow-up windows, cooldown periods, and review checkpoints in a deterministic local planner so work does not miss critical dates.

## 8.2 Supported responsibilities

- [x] Store normalized deadlines and reminder checkpoints.
- [x] Track deadline source/provenance.
- [x] Track cooldown and retry windows.
- [x] Surface overdue, upcoming, and stale items.
- [x] Expose queue-planning summaries for orchestrator/skills.

## 8.3 Hard boundaries

- [x] Do not send emails or notifications directly unless explicitly routed through an approved governor later.
- [x] Do not infer deadlines from ambiguous text without marking them uncertain.
- [x] Do not silently drop expired or conflicting deadlines.

## 8.4 Implementation tasks

- [x] Define typed deadline item and reminder summary models.
- [x] Add timezone-aware normalization rules.
- [x] Add provenance and confidence metadata.
- [x] Add overdue and upcoming query helpers.
- [x] Add conflict detection for competing deadlines.
- [x] Add audit events for changed or invalidated deadlines.
- [x] Add evidence linkage back to source snapshots.

## 8.5 Tests

- [x] Explicit deadline parsing succeeds.
- [x] Ambiguous deadline becomes review-required or uncertain.
- [x] Overdue item detection works.
- [x] Cooldown window tracking works.
- [x] Conflicting deadlines are surfaced explicitly.

## 8.6 Acceptance criteria

- [x] Queue-planning and follow-up skills have deterministic schedule state.
- [x] Ambiguous dates fail closed instead of becoming fake certainty.

---

# 9. P1 - Implement `download_quarantine_plugin`

## 9.1 Goal

Safely ingest downloaded files and attachments into a bounded quarantine pipeline before any other skill or plugin treats them as trusted inputs.

## 9.2 Supported responsibilities

- [x] Download from allowlisted URLs or ingest mailbox attachments.
- [x] Enforce size, extension, MIME, and magic-byte checks.
- [x] Hash and stage files under a quarantine directory.
- [x] Record safe metadata and provenance.
- [x] Allow deterministic promotion to archived evidence only after validation.

## 9.3 Hard boundaries

- [x] Do not execute downloaded files.
- [x] Do not auto-open office documents, PDFs, or binaries.
- [x] Do not allow path traversal or archive extraction outside the quarantine root.
- [x] Do not allow unsupported executable or script content by default.

## 9.4 Implementation tasks

- [x] Define quarantine root and path rules.
- [x] Define typed ingest, scan, and promotion result models.
- [x] Add content-type, extension, and signature validation.
- [x] Add archive/zip handling rules with entry-count and nested-size caps.
- [x] Add hash generation and metadata sidecars.
- [x] Add deterministic promotion workflow into the evidence archive.
- [x] Add audit events for rejected or suspicious files.

## 9.5 Tests

- [x] Safe small file ingestion succeeds.
- [x] Unsupported executable content is rejected.
- [x] Oversized file is rejected.
- [x] Path traversal attempt is rejected.
- [x] Zip bomb-like input is rejected.
- [x] Promotion preserves hash identity and provenance.

## 9.6 Acceptance criteria

- [x] Attachments and downloads are treated as untrusted until validated.
- [x] Dangerous file handling stays constrained and auditable.

---

# 10. P2 - Implement `counterparty_snapshot_plugin`

## 10.1 Goal

Collect and normalize public counterparty evidence snapshots so risk profiling can rely on archived facts instead of one-off browsing or memory.

## 10.2 Supported responsibilities

- [ ] Capture public profile/about/payment-proof pages from allowlisted sources.
- [ ] Normalize stable identity and reputation indicators.
- [ ] Archive public evidence snapshots and hashes.
- [ ] Surface freshness and provenance metadata.
- [ ] Support deterministic comparison of repeated observations over time.

## 10.3 Hard boundaries

- [ ] Do not log in to personal accounts.
- [ ] Do not scrape disallowed or non-allowlisted sites.
- [ ] Do not bypass robots/terms restrictions that the project should respect.
- [ ] Do not treat unverifiable claims as facts.

## 10.4 Implementation tasks

- [ ] Define allowlisted source categories.
- [ ] Define typed snapshot request/result models.
- [ ] Add field extraction for stable public indicators.
- [ ] Add provenance and freshness tracking.
- [ ] Add comparison helpers for changed public signals.
- [ ] Add evidence archival and ledger linkage.

## 10.5 Tests

- [ ] Supported public snapshot capture succeeds.
- [ ] Non-allowlisted source is rejected.
- [ ] Missing expected public fields are surfaced as incomplete.
- [ ] Freshness metadata is preserved.
- [ ] Repeated capture comparison behaves deterministically.

## 10.6 Acceptance criteria

- [ ] Counterparty-risk analysis can rely on archived public evidence.
- [ ] The plugin stays within low-risk public-data boundaries.

---

# 11. P2 - Implement `metrics_export_plugin`

## 11.1 Goal

Provide deterministic local export and summary generation for experiment, payout, and review metrics without giving the LLM raw unrestricted database access.

## 11.2 Supported responsibilities

- [ ] Export predefined accounting/review/report datasets.
- [ ] Produce bounded summary inputs for review and strategy skills.
- [ ] Track export job metadata and artifact paths.
- [ ] Support CSV/JSON outputs where already accepted by the repo.
- [ ] Provide filters for date range, opportunity class, and outcome category.

## 11.3 Hard boundaries

- [ ] Do not expose arbitrary SQL or arbitrary filesystem read access.
- [ ] Do not export secrets or raw sensitive config values.
- [ ] Do not allow unbounded full-ledger dumps through the skill interface by default.

## 11.4 Implementation tasks

- [ ] Define approved export shapes and filter options.
- [ ] Define typed export request/result models.
- [ ] Add bounded query builders over existing ledger APIs/helpers.
- [ ] Add output file generation with stable ordering.
- [ ] Add evidence/archive linkage for exported reports where needed.
- [ ] Add audit events for export jobs and failures.

## 11.5 Tests

- [ ] Approved export succeeds with stable output ordering.
- [ ] Unsupported filter is rejected.
- [ ] Sensitive fields are excluded.
- [ ] Oversized export request is rejected or bounded safely.
- [ ] Export metadata and audit linkage are preserved.

## 11.6 Acceptance criteria

- [ ] Review and strategy flows can consume bounded historical summaries safely.
- [ ] Export behavior is deterministic and auditable.

---

# 12. Cross-cutting implementation tasks

## 12.1 Documentation

- [ ] Add or update plugin-specific docs for every new plugin.
  - [ ] goal
  - [ ] authority boundaries
  - [ ] inputs/outputs
  - [ ] config
  - [ ] failure modes
  - [ ] tests
  - [ ] acceptance criteria
- [ ] Update architecture docs if any new plugin changes the supported service/plugin map.
- [ ] Document which plugins are optional, disabled by default, or read-only only.

## 12.2 Quality gates

- [ ] Add unit tests for each new plugin module.
- [ ] Add integration tests for service boundaries and orchestration handoffs.
- [ ] Add fixture coverage for malformed inputs and hostile/untrusted external content.
- [ ] Run:
  - [ ] `uv run --python 3.11 ruff check .`
  - [ ] `uv run --python 3.11 mypy .`
  - [ ] `uv run --python 3.11 pytest`

## 12.3 Safety review pass

- [ ] Verify no new plugin bypasses `wallet_governor_service`.
- [ ] Verify no new plugin bypasses `ledger_skill` or approved ledger APIs for durable records.
- [ ] Verify no new plugin bypasses `receipt_and_evidence_archiver` for evidence storage.
- [ ] Verify no new plugin adds hidden send, submit, or login capabilities.
- [ ] Verify all new plugins fail closed when unavailable or misconfigured.
- [ ] Verify allowlists, size limits, and path checks exist anywhere external content is handled.

## 12.4 Orchestration and rollout

- [ ] Add feature flags or config gating for optional plugins.
- [ ] Ensure optional plugin absence does not create unsafe fallback behavior.
- [ ] Ensure required plugin absence blocks dependent skills cleanly.
- [ ] Add startup validation for required plugin configs.
- [ ] Add health reporting for service-style plugins.

---

# 13. Suggested implementation phases

## Phase A - P0 safety and prerequisite plugins

- [x] `operator_profile_store`
- [x] `rules_snapshot_gateway`
- [x] `wallet_observer_plugin`
- [x] `inbox_observer_plugin`

## Phase B - P1 execution-readiness plugins

- [x] `opportunity_index_plugin`
- [x] `artifact_renderer_plugin`
- [x] `deadline_scheduler_plugin`
- [x] `download_quarantine_plugin`

## Phase C - P2 intelligence and reporting plugins

- [ ] `counterparty_snapshot_plugin`
- [ ] `metrics_export_plugin`

## Phase D - Final hardening

- [ ] update docs
- [ ] run lint/type/tests
- [ ] complete integration coverage
- [ ] verify fail-closed behavior
- [ ] update master TODOs if needed

---

# 14. Final acceptance criteria

- [ ] All new plugins are first-party and repository-owned.
- [ ] All new plugins have narrow, documented authority boundaries.
- [ ] No new plugin exposes spend, login, send, or submission power without an existing governor boundary.
- [ ] Every plugin has typed contracts, explicit error behavior, and tests.
- [ ] Every plugin that handles external content uses allowlists, size limits, and path safety checks.
- [ ] Plugin outputs can be linked to ledger and evidence records where applicable.
- [ ] Optional plugins are disabled or read-only by default when appropriate.
- [ ] The plugin wave improves eligibility checks, terms freshness, payout follow-up, duplicate detection, submission packaging, and review analytics without expanding unsafe autonomy.
