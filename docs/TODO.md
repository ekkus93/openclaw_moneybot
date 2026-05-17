# OpenClaw MoneyBot Master TODO

This is the top-level implementation tracker for the project. Use it to manage overall sequencing, cross-cutting work, and milestone progress.

For detailed implementation checklists, see the skill and plugin TODO files under `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/`.

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

- [ ] Implement `email_drafter` in v1 draft-only mode.
  - [ ] Add structured request/result models
  - [ ] Add safe template support
  - [ ] Add compliance checks
  - [ ] Archive drafts and link them to ledger/evidence
- [ ] Enforce communication rules.
  - [ ] No mass outreach
  - [ ] No deceptive identity
  - [ ] No fake affiliation
  - [ ] No unsupported claims
  - [ ] No repeated harassment loops
  - [ ] No sending in v1
- [ ] Add tests for allowed draft generation and blocked misuse patterns.
- [ ] Track detailed work in:
  - [ ] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/email_drafter/TODO.md`

## Phase 9 - Wallet governor service

- [ ] Implement `wallet_governor_service` as the only wallet-facing component.
  - [ ] Keep service local-only
  - [ ] Add health, balance, limits, quote, and capped send endpoints
  - [ ] Load secrets only in the service boundary
  - [ ] Never expose passphrases, RPC cookies, private keys, or backups
- [ ] Enforce hard spend rules.
  - [ ] Max single payment
  - [ ] Max daily payment
  - [ ] Max weekly payment
  - [ ] No `send-all`
  - [ ] Required purpose/counterparty/destination
  - [ ] Required policy, budget, and ledger references
  - [ ] Idempotency and duplicate protection
- [ ] Add wallet integration protections.
  - [ ] Localhost-only RPC/service access
  - [ ] Minimal wallet unlock time
  - [ ] Immediate lock after spend attempt
  - [ ] Safe logging only
- [ ] Add fake-backend and, later, limited integration testing.
- [ ] Track detailed work in:
  - [ ] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/plugins/wallet_governor_service_TODO.md`

## Phase 10 - Wallet governor client

- [ ] Implement `wallet_governor_client`.
  - [ ] Add balance, quote, and spend request models
  - [ ] Add client-side preflight validation
  - [ ] Restrict base URL to localhost unless explicitly configured
  - [ ] Default to read-only or spend-disabled mode
- [ ] Enforce client-side safeguards.
  - [ ] Reject missing policy/budget/ledger references
  - [ ] Reject invalid or missing destination
  - [ ] Reject unsupported assets
  - [ ] Reject over-limit requests before HTTP call
  - [ ] Reject any `send_all` style request
- [ ] Write all outcomes back to ledger.
  - [ ] Successful send
  - [ ] Explicit rejection
  - [ ] Service errors/timeouts
- [ ] Add tests with fake service responses.
- [ ] Track detailed work in:
  - [ ] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/wallet_governor_client/TODO.md`

## Phase 11 - Experiment review and feedback loop

- [ ] Implement `experiment_reviewer`.
  - [ ] Pull experiment context from ledger and evidence
  - [ ] Calculate spend, revenue, ROI, time spent, and status
  - [ ] Produce deterministic `continue`, `stop`, `retry_with_changes`, or `human_review`
- [ ] Feed lessons back into the system.
  - [ ] Opportunity scoring feedback
  - [ ] Policy pattern feedback
  - [ ] Budget estimation feedback
- [ ] Archive and ledger the review result.
- [ ] Add tests for profitable, failed, ambiguous, and unsafe cases.
- [ ] Track detailed work in:
  - [ ] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/experiment_reviewer/TODO.md`

## Phase 12 - Optional local service layer

- [ ] Decide whether `ledger_api` is needed for local service boundaries.
  - [ ] If yes, implement narrow local-only endpoints or module functions
  - [ ] Restrict writes to known schemas only
  - [ ] Reject arbitrary SQL
  - [ ] Preserve idempotency and tamper-evident integrity
- [ ] Defer optional `email_governor` until draft-only mode is solid.
- [ ] Defer any browser governor until policy, archive, and workflow controls are proven.
- [ ] Track detailed work in:
  - [ ] `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/plugins/ledger_api_TODO.md`

## Phase 13 - Orchestration and end-to-end workflow

- [ ] Implement the default workflow wiring.
  - [ ] `opportunity_scout`
  - [ ] `moneybot_policy_guard`
  - [ ] `tos_legal_checker`
  - [ ] `budget_and_roi_planner`
  - [ ] `moneybot_policy_guard` re-check for execution
  - [ ] `ledger_skill`
  - [ ] Execution-adjacent skill calls
  - [ ] `wallet_governor_client` if needed and approved
  - [ ] `receipt_and_evidence_archiver`
  - [ ] `ledger_skill` final outputs
  - [ ] `experiment_reviewer`
- [ ] Implement one complete dry-run path first.
  - [ ] No real spending
  - [ ] No real sending
  - [ ] Full ledger trail
  - [ ] Full evidence trail
- [ ] Only after dry-run success, implement one tiny real-wallet payment path under strict limits.

## Phase 14 - Acceptance, testing, and operational readiness

- [ ] Add or confirm offline unit tests for every skill and service.
- [ ] Add integration tests for the end-to-end dry-run workflow.
- [ ] Add integration tests for blocked/fail-closed wallet cases.
- [ ] Add startup validation and safe defaults.
  - [ ] Wallet spending disabled by default
  - [ ] Email sending disabled by default
  - [ ] Unknown categories default to `needs_review`
  - [ ] Missing config fails closed
- [ ] Add operator documentation.
  - [ ] How to set up the local environment with `uv`
  - [ ] How to run `ruff`
  - [ ] How to run `mypy`
  - [ ] How to run `pytest`
  - [ ] How to run a dry-run mission
  - [ ] How to enable/disable wallet spending
- [ ] Confirm v1 acceptance criteria.
  - [ ] All nine skill specs and implementation TODOs exist
  - [ ] Ledger stores required records
  - [ ] Policy guard blocks prohibited categories
  - [ ] Evidence archive stores and links artifacts
  - [ ] Email remains draft-only in v1
  - [ ] Wallet spending cannot bypass policy, budget, ledger, or service limits
  - [ ] The project can complete one full dry-run and one tiny capped payment test

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
