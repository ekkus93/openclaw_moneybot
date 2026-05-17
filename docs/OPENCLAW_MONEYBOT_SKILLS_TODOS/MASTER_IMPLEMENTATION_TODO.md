# OpenClaw MoneyBot Skill Implementation TODOs

These TODO files are implementation handoff documents for building the OpenClaw MoneyBot skills from the existing `SKILL.md` specifications.

Assumptions:

- Python implementation is acceptable unless the repo dictates another language.
- Use Pydantic v2 for typed contracts and validation.
- Use SQLite for durable local state and tests.
- Prefer deterministic rule engines over LLM-only judgment for safety-critical decisions.
- Do not use external commercial LLM APIs. The bot will use the user's local LLM.
- Do not give OpenClaw direct access to private keys, wallet passphrases, raw Bitcoin RPC credentials, personal accounts, or unrestricted shell access.
- Every externally meaningful action must be written to the ledger before execution.

## Master implementation TODO

### Phase 0 — Repository and project scaffolding

- [ ] Create or confirm the target repository layout.
  - [ ] Add `skills/` if it does not exist.
  - [ ] Add one subdirectory per MoneyBot skill.
  - [ ] Preserve the existing `SKILL.md` files exactly unless a task explicitly updates them.
  - [ ] Add implementation code outside `SKILL.md` so the spec remains readable.
- [ ] Add a project-level `pyproject.toml` if one does not already exist.
  - [ ] Use Python 3.11+ unless the existing OpenClaw environment requires another version.
  - [ ] Add dependencies: `pydantic>=2`, `pytest`, `pytest-cov`, `ruff`, and a lightweight HTTP client if needed.
  - [ ] Use `sqlite3` from the standard library unless SQLAlchemy is already standard in the repo.
- [ ] Add a project-level test folder.
  - [ ] Use real SQLite temp databases in tests, not mocks.
  - [ ] Use local fixture files for HTML, JSON, email messages, and wallet-governor responses.
  - [ ] Do not require network access for unit tests.
- [ ] Add a shared contracts module.
  - [ ] Define common Pydantic models for `MoneyBotAction`, `PolicyDecision`, `Opportunity`, `BudgetPlan`, `LedgerRecord`, `SpendRequest`, `EvidenceRecord`, and `ExperimentReview`.
  - [ ] Make all timestamps timezone-aware ISO-8601 strings or `datetime` objects serialized consistently.
  - [ ] Define enums for risk levels, decision states, action categories, spend categories, and blocked categories.
  - [ ] Add schema tests that validate representative JSON examples from every skill.
- [ ] Add a shared error model.
  - [ ] Include `error_code`, `message`, `recoverable`, `details`, and `safe_for_user`.
  - [ ] Ensure skills return structured errors instead of unstructured exceptions.

### Phase 1 — Safety and state foundation

- [ ] Implement `ledger_skill` first.
  - [ ] Create migrations/schema.
  - [ ] Add append-only records.
  - [ ] Add idempotency keys.
  - [ ] Add tests for duplicate prevention and tamper-evident record hashes.
- [ ] Implement `moneybot_policy_guard` second.
  - [ ] Create deterministic rule taxonomy.
  - [ ] Block prohibited categories by default.
  - [ ] Require explicit human review for uncertain financial/legal categories.
- [ ] Implement evidence archival before external execution.
  - [ ] Archive source pages, rules, proposals, receipts, email drafts, and transaction metadata.
  - [ ] Link all evidence records back to ledger IDs.

### Phase 2 — Research and decision skills

- [ ] Implement `tos_legal_checker`.
  - [ ] Start with static/local page ingestion and fixture-driven tests.
  - [ ] Add live browsing only behind explicit OpenClaw tool boundaries.
  - [ ] Make uncertainty produce `human_review`, not `allow`.
- [ ] Implement `budget_and_roi_planner`.
  - [ ] Require max loss, expected value, stop condition, success metric, and total budget impact.
  - [ ] Make `execute` impossible unless policy and TOS dependencies are satisfied.
- [ ] Implement `opportunity_scout`.
  - [ ] Produce candidate opportunities only.
  - [ ] Do not give it wallet, email-send, or purchasing power.
  - [ ] Require dedupe, scoring, evidence links, and downstream handoff records.

### Phase 3 — Execution-adjacent skills

- [ ] Implement `email_drafter` in draft-only mode first.
  - [ ] No autonomous sending in v1.
  - [ ] Add strict anti-spam and non-deception checks.
  - [ ] Require policy approval before producing outbound commercial outreach.
- [ ] Implement `wallet_governor_client` after the wallet-governor service exists.
  - [ ] Never expose raw wallet credentials or raw Bitcoin RPC to the skill.
  - [ ] Add client-side validation, but rely on the service for final enforcement.
  - [ ] Require ledger pre-write before spend execution.
- [ ] Implement `experiment_reviewer` last.
  - [ ] Pull data from ledger, evidence archive, and spend records.
  - [ ] Produce continue/stop/retry decisions.
  - [ ] Add feedback into opportunity scoring and blocked-pattern lists.

### Phase 4 — Integration pipeline

- [ ] Implement a single end-to-end dry-run workflow:
  - [ ] `opportunity_scout` finds candidates.
  - [ ] `tos_legal_checker` evaluates the best candidate.
  - [ ] `moneybot_policy_guard` approves or blocks the planned action.
  - [ ] `budget_and_roi_planner` creates an experiment plan.
  - [ ] `ledger_skill` records the plan.
  - [ ] `email_drafter` drafts any required message.
  - [ ] `receipt_and_evidence_archiver` stores all source/evidence artifacts.
  - [ ] `experiment_reviewer` reviews the simulated outcome.
- [ ] Implement a limited spend workflow only after dry-run passes.
  - [ ] Require a real ledger entry before wallet call.
  - [ ] Require policy approval ID and budget plan ID.
  - [ ] Require wallet-governor service to enforce max single spend and daily spend.
  - [ ] Require receipt/evidence record after spend.
- [ ] Add an integration test using fake local wallet-governor service responses.
  - [ ] Test allowed tiny payment.
  - [ ] Test blocked over-limit payment.
  - [ ] Test blocked prohibited category payment.
  - [ ] Test missing ledger pre-write.

### Phase 5 — Configuration and deployment

- [ ] Add `moneybot.yaml` config.
  - [ ] Configure max spend limits.
  - [ ] Configure blocked categories.
  - [ ] Configure evidence archive path.
  - [ ] Configure SQLite database path.
  - [ ] Configure wallet-governor URL.
  - [ ] Configure email mode: `draft_only` by default.
- [ ] Add safe defaults.
  - [ ] Default wallet spending disabled.
  - [ ] Default email sending disabled.
  - [ ] Default browser purchasing/form-submit disabled.
  - [ ] Default unknown action category to `needs_review`.
- [ ] Add startup validation.
  - [ ] Fail closed if ledger DB is unavailable.
  - [ ] Fail closed if policy config is missing.
  - [ ] Fail closed if wallet-governor limits cannot be fetched.
- [ ] Add runbook documentation.
  - [ ] Explain how to run tests.
  - [ ] Explain how to run a dry-run mission.
  - [ ] Explain how to enable wallet spending.
  - [ ] Explain how to disable wallet spending immediately.

### Phase 6 — Acceptance criteria

- [ ] No skill can send money directly.
- [ ] No skill can access private keys, seed phrases, wallet backups, or wallet passphrases.
- [ ] No skill can approve its own prohibited-category action.
- [ ] Every spend requires a policy decision, budget plan, ledger entry, and wallet-governor approval.
- [ ] Every opportunity has an evidence trail.
- [ ] Every external message is either draft-only or rate-limited through a governor.
- [ ] All unit tests pass offline.
- [ ] Integration tests prove blocked actions fail closed.
- [ ] The bot can complete a full no-money dry run from opportunity discovery to experiment review.
