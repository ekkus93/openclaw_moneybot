# OpenClaw MoneyBot Master TODO

This is the top-level implementation tracker for the project. Use it to manage overall sequencing, cross-cutting work, and milestone progress.

For detailed implementation checklists, see the skill and plugin TODO files under `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/`.

## Current status

- [x] Core phases 0-15 are implemented.
- [x] The SKILLS1 first-party skill wave is implemented and validated:
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
- [x] The repository currently passes `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest`.

## Read first

- `docs/OPENCLAW_MONEYBOT_PROJECT_SPEC.md`
- `docs/OPENCLAW_MONEYBOT_ARCHITECTURE.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md`

## Project guardrails

- [ ] Keep the system as a **bounded experiment runner**, not a general-purpose autonomous finance agent.
- [ ] Preserve the layered architecture: local LLM -> orchestration -> narrow skills -> deterministic validators/schemas -> governed services -> local ledger/archive/wallet/email.
- [ ] Keep wallet access behind `wallet_governor_service` only.
- [ ] Keep ledger writes behind `ledger_skill` or a narrow ledger API only.
- [ ] Keep evidence storage behind `receipt_and_evidence_archiver` only.
- [ ] Fail closed on uncertainty, malformed model output, missing config, and missing approvals.
- [ ] Preserve complete auditability for opportunities, policy decisions, plans, spends, messages, artifacts, and reviews.
- [ ] Enforce the non-goals from the project spec, especially no trading, gambling, fake identities, spam, phishing, malware, or handling money for other people.

## Recommended implementation order

- [ ] Foundation first: `ledger_skill`
- [ ] Then: `moneybot_policy_guard`
- [ ] Then: `receipt_and_evidence_archiver`
- [ ] Then: `tos_legal_checker`
- [ ] Then: `budget_and_roi_planner`
- [ ] Then: `opportunity_scout`
- [ ] Then: `email_drafter`
- [ ] Then: `wallet_governor_service`
- [ ] Then: `wallet_governor_client`
- [ ] Then: `experiment_reviewer`
- [ ] Then: orchestration and end-to-end workflows

## Phase 0 - Repository and tooling foundation

- [x] Create or confirm the Python project scaffold.
  - [x] Use **Python 3.11**.
  - [x] Use **uv** for environment and dependency management.
  - [x] Add or confirm `pyproject.toml`.
  - [x] Add or confirm package layout under `src/openclaw_moneybot/`.
  - [x] Add or confirm `tests/` layout for unit, integration, and fixtures.
- [x] Configure the required quality gates.
  - [x] Add **ruff** configuration.
  - [x] Add **mypy** configuration.
  - [x] Add **pytest** configuration.
  - [x] Ensure lint and type errors are fixed, not ignored or suppressed.
- [x] Add foundational dependencies only as needed.
  - [x] `pydantic>=2`
  - [x] HTTP client library for local service calls
  - [x] Test utilities/fixtures
- [x] Establish repository conventions.
  - [x] Keep specs in `SKILL.md` files readable and separate from implementation code.
  - [x] Keep services separately testable from orchestration code.
  - [x] Keep unit tests offline and fixture-driven.

## Phase 1 - Shared contracts, config, and errors

- [x] Create shared schema/contracts modules.
  - [x] Common IDs and timestamp handling
  - [x] Risk levels, decision enums, and action categories
  - [x] Opportunity, policy, TOS/legal, budget, spend, evidence, email, and review models
- [x] Create shared config models and loaders.
  - [x] MoneyBot policy config
  - [x] Ledger config
  - [x] Archive config
  - [x] Wallet governor client/service config
  - [x] Email mode config
- [x] Create a shared structured error model.
  - [x] Stable error codes
  - [x] Safe user-facing messages
  - [x] Recoverability metadata
  - [x] Validation error formatting
- [x] Add shared tests.
  - [x] Schema validation tests
  - [x] Config validation tests
  - [x] Serialization consistency tests

## Phase 2 - Ledger foundation

- [x] Implement the SQLite ledger as the local system of record.
  - [x] Create schema and migrations
  - [x] Add append-oriented tables
  - [x] Add foreign keys and indexes
  - [x] Add idempotency support
  - [x] Add tamper-evident event hashing
- [x] Implement ledger operations for all major record types.
  - [x] Opportunities
  - [x] Policy decisions
  - [x] TOS/legal checks
  - [x] Budget plans
  - [x] Spend requests
  - [x] Wallet transactions
  - [x] Email drafts/events
  - [x] Evidence artifacts
  - [x] Experiment reviews
  - [x] Audit events
- [x] Implement read/query helpers.
  - [x] Opportunity timeline
  - [x] Daily/weekly spend totals
  - [x] Exportable accounting/tax views
- [x] Add tests for:
  - [x] Migrations
  - [x] Idempotency
  - [x] Hash-chain verification
  - [x] Foreign key enforcement
  - [x] Duplicate prevention
  - [x] CSV/JSONL export if added
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/ledger_skill/TODO.md`
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/plugins/ledger_api_TODO.md`

## Phase 3 - Deterministic policy guard

- [x] Implement `moneybot_policy_guard` as the central gatekeeper.
  - [x] Define the deterministic taxonomy of allowed, blocked, and review-required categories
  - [x] Encode hard-block rules first
  - [x] Encode missing-information rules
  - [x] Encode explicit allow rules only for low-risk actions
- [x] Enforce policy requirements for dangerous actions.
  - [x] Spending
  - [x] Email sending
  - [x] Browser form submission
  - [x] Account creation
  - [x] Publishing content
  - [x] Shell operations that touch sensitive areas
- [x] Include structured policy outputs.
  - [x] Decision
  - [x] Risk level
  - [x] Matched rules
  - [x] Mitigations
  - [x] Human review reason
  - [x] Expiration/version metadata
- [x] Add tests for blocked, review-required, and allowed paths.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/moneybot_policy_guard/TODO.md`

## Phase 4 - Evidence archive

- [x] Implement `receipt_and_evidence_archiver`.
  - [x] Create immutable local archive layout
  - [x] Store metadata sidecars
  - [x] Hash archived artifacts
  - [x] Add verification helpers
- [x] Support core evidence types.
  - [x] Opportunity page snapshots
  - [x] TOS/rules snapshots
  - [x] Budget plan snapshots
  - [x] Policy decision snapshots
  - [x] Email drafts
  - [x] Invoices and receipts
  - [x] Wallet transaction metadata
  - [x] Deliverables and payout proof
  - [x] Experiment review snapshots
- [x] Add secret/privacy protections.
  - [x] Redact accidentally captured secrets
  - [x] Record redaction events
  - [x] Reject unsafe paths
- [x] Link all archived artifacts back to ledger records.
- [x] Add tests for immutability, hashing, path safety, and redaction.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/receipt_and_evidence_archiver/TODO.md`

## Phase 5 - Rules, terms, and legal review

- [x] Implement `tos_legal_checker`.
  - [x] Build input/output contracts
  - [x] Support local evidence-driven extraction first
  - [x] Extract rules relevant to eligibility, payment, automation, outreach, account use, and data handling
  - [x] Produce structured `proceed`, `reject`, or `human_review` results
- [x] Add deterministic checks for:
  - [x] Bot/automation prohibitions
  - [x] Commercial-use prohibitions
  - [x] Fake identity requirements
  - [x] Spam/outreach restrictions
  - [x] Regulated-finance indicators
  - [x] Unclear payment mechanisms
  - [x] Missing or ambiguous rules
- [x] Link output to evidence archive and ledger.
- [x] Produce handoff data for policy evaluation.
- [x] Add fixture-based tests for allowed, blocked, and ambiguous cases.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/tos_legal_checker/TODO.md`

## Phase 6 - Budgeting and bounded experiment design

- [x] Implement `budget_and_roi_planner`.
  - [x] Require policy and TOS/legal prerequisites
  - [x] Require explicit spend, max loss, revenue estimate, fees, success metric, stop condition, and timebox
  - [x] Calculate net outcome and budget impact deterministically
- [x] Add decision logic for:
  - [x] `reject`
  - [x] `simulate`
  - [x] `execute_request`
  - [x] `human_review`
- [x] Produce downstream records.
  - [x] Ledger-ready budget/experiment plan
  - [x] Wallet-governor request payload only when all gates pass
  - [x] Evidence expectations
- [x] Add tests for over-limit, recurring billing, unknown fees, and missing prerequisites.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/budget_and_roi_planner/TODO.md`

## Phase 7 - Opportunity discovery

- [x] Implement `opportunity_scout` as a research-only skill.
  - [x] Define supported source categories
  - [x] Define unsupported/prohibited categories
  - [x] Extract structured candidate data
  - [x] Deduplicate candidates
  - [x] Score and rank candidates deterministically
- [x] Preserve strict limits.
  - [x] No spending
  - [x] No email sending
  - [x] No account creation
  - [x] No form submission
  - [x] No commitment to opportunities
- [x] Produce downstream handoffs.
  - [x] TOS/legal check requests
  - [x] Ledger-ready opportunity discovery records
  - [x] Evidence references where available
- [x] Add tests for extraction, rejection, dedupe, and ranking.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/opportunity_scout/TODO.md`

## Phase 8 - Draft-only communications

- [x] Implement `email_drafter` in v1 draft-only mode.
  - [x] Add structured request/result models
  - [x] Add safe template support
  - [x] Add compliance checks
  - [x] Archive drafts and link them to ledger/evidence
- [x] Enforce communication rules.
  - [x] No mass outreach
  - [x] No deceptive identity
  - [x] No fake affiliation
  - [x] No unsupported claims
  - [x] No repeated harassment loops
  - [x] No sending in v1
- [x] Add tests for allowed draft generation and blocked misuse patterns.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/email_drafter/TODO.md`

## Phase 9 - Wallet governor service

- [x] Implement `wallet_governor_service` as the only wallet-facing component.
  - [x] Keep service local-only
  - [x] Add health, balance, limits, quote, and capped send endpoints
  - [x] Load secrets only in the service boundary
  - [x] Never expose passphrases, RPC cookies, private keys, or backups
- [x] Enforce hard spend rules.
  - [x] Max single payment
  - [x] Max daily payment
  - [x] Max weekly payment
  - [x] No `send-all`
  - [x] Required purpose/counterparty/destination
  - [x] Required policy, budget, and ledger references
  - [x] Idempotency and duplicate protection
- [x] Add wallet integration protections.
  - [x] Localhost-only RPC/service access
  - [x] Minimal wallet unlock time
  - [x] Immediate lock after spend attempt
  - [x] Safe logging only
- [x] Add fake-backend and, later, limited integration testing.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/plugins/wallet_governor_service_TODO.md`

## Phase 10 - Wallet governor client

- [x] Implement `wallet_governor_client`.
  - [x] Add balance, quote, and spend request models
  - [x] Add client-side preflight validation
  - [x] Restrict base URL to localhost unless explicitly configured
  - [x] Default to read-only or spend-disabled mode
- [x] Enforce client-side safeguards.
  - [x] Reject missing policy/budget/ledger references
  - [x] Reject invalid or missing destination
  - [x] Reject unsupported assets
  - [x] Reject over-limit requests before HTTP call
  - [x] Reject any `send_all` style request
- [x] Write all outcomes back to ledger.
  - [x] Successful send
  - [x] Explicit rejection
  - [x] Service errors/timeouts
- [x] Add tests with fake service responses.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/wallet_governor_client/TODO.md`

## Phase 11 - Experiment review and feedback loop

- [x] Implement `experiment_reviewer`.
  - [x] Pull experiment context from ledger and evidence
  - [x] Calculate spend, revenue, ROI, time spent, and status
  - [x] Produce deterministic `continue`, `stop`, `retry_with_changes`, or `human_review`
- [x] Feed lessons back into the system.
  - [x] Opportunity scoring feedback
  - [x] Policy pattern feedback
  - [x] Budget estimation feedback
- [x] Archive and ledger the review result.
- [x] Add tests for profitable, failed, ambiguous, and unsafe cases.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/experiment_reviewer/TODO.md`

## Phase 12 - Optional local service layer

- [x] Decide whether `ledger_api` is needed for local service boundaries.
  - [x] If yes, implement narrow local-only endpoints or module functions
  - [x] Restrict writes to known schemas only
  - [x] Reject arbitrary SQL
  - [x] Preserve idempotency and tamper-evident integrity
- [x] Defer optional `email_governor` until draft-only mode is solid.
- [x] Defer any browser governor until policy, archive, and workflow controls are proven.
- [x] Track detailed work in:
  - [x] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/plugins/ledger_api_TODO.md`

## Phase 13 - Orchestration and end-to-end workflow

- [x] Implement the default workflow wiring.
  - [x] `opportunity_scout`
  - [x] `moneybot_policy_guard`
  - [x] `tos_legal_checker`
  - [x] `budget_and_roi_planner`
  - [x] `moneybot_policy_guard` re-check for execution
  - [x] `ledger_skill`
  - [x] Execution-adjacent skill calls
  - [x] `wallet_governor_client` if needed and approved
  - [x] `receipt_and_evidence_archiver`
  - [x] `ledger_skill` final outputs
  - [x] `experiment_reviewer`
- [x] Implement one complete dry-run path first.
  - [x] No real spending
  - [x] No real sending
  - [x] Full ledger trail
  - [x] Full evidence trail
- [x] Only after dry-run success, implement one tiny real-wallet payment path under strict limits.

## Phase 14 - Acceptance, testing, and operational readiness

- [x] Add or confirm offline unit tests for every skill and service.
- [x] Add integration tests for the end-to-end dry-run workflow.
- [x] Add integration tests for blocked/fail-closed wallet cases.
- [x] Add startup validation and safe defaults.
  - [x] Wallet spending disabled by default
  - [x] Email sending disabled by default
  - [x] Unknown categories default to `needs_review`
  - [x] Missing config fails closed
- [x] Add operator documentation.
  - [x] How to set up the local environment with `uv`
  - [x] How to run `ruff`
  - [x] How to run `mypy`
  - [x] How to run `pytest`
  - [x] How to run a dry-run mission
  - [x] How to enable/disable wallet spending
- [x] Confirm v1 acceptance criteria.
  - [x] All nine skill specs and implementation TODOs exist
  - [x] Ledger stores required records
  - [x] Policy guard blocks prohibited categories
  - [x] Evidence archive stores and links artifacts
  - [x] Email remains draft-only in v1
  - [x] Wallet spending cannot bypass policy, budget, ledger, or service limits
  - [x] The project can complete one full dry-run and one tiny capped payment test

## Detailed TODO references

### Master handoff docs

- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/README.md`

### Skill TODOs

- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/ledger_skill/TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/moneybot_policy_guard/TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/receipt_and_evidence_archiver/TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/tos_legal_checker/TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/budget_and_roi_planner/TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/opportunity_scout/TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/email_drafter/TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/wallet_governor_client/TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/experiment_reviewer/TODO.md`

### Plugin/service TODOs

- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/plugins/wallet_governor_service_TODO.md`
- `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/plugins/ledger_api_TODO.md`

## Suggested first implementation slice

- [ ] Set up the Python 3.11 / uv / ruff / mypy / pytest foundation.
- [ ] Add shared contracts, config loading, and structured errors.
- [ ] Build `ledger_skill` first.
- [ ] Then build `moneybot_policy_guard`.
- [ ] Then build `receipt_and_evidence_archiver`.

That first slice gives the project a safe, auditable foundation before any execution-adjacent behavior is added.
