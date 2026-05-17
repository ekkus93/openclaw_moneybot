# OpenClaw MoneyBot Implementation TODO

High-level, comprehensive task list. Use this as the primary planning file.

Notes:
- Python 3.11.
- Use uv for environment and dependency management.
- Use ruff for linting and formatting.
- Use mypy for type checking.
- Use pytest for unit tests.
- All lint/type/test warnings must be fixed, never ignored or silenced.

Reference:
- docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md
- docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/README.md

## Phase 0 — Repository and project scaffolding

- [x] Create project root layout
  - [x] Set up Python 3.11 project with uv (pyproject.toml, uv lock, etc.)
  - [x] Add ruff, mypy, pytest, pydantic, httpx/requests-like client, and sqlite3
  - [x] Add directories:
    - [x] skills/
    - [x] plugins/
    - [x] shared/
    - [x] tests/
    - [x] configs/
    - [x] scripts/
- [x] Integrate SKILL.md files
  - [x] Preserve existing SKILL.md files as-is.
  - [x] Map each SKILL.md to its implementation directory.
- [x] Add linting, typing, testing config
  - [x] Configure ruff for linting and formatting.
  - [x] Configure mypy for strict type checking.
  - [x] Configure pytest for unit and integration tests.
  - [x] Ensure CI/Makefile/Makefile-like scripts for:
    - [x] lint
    - [x] type-check
    - [x] test
    - [x] format
- [x] Add shared contracts and error model
  - [x] Define common Pydantic models (MoneyBotAction, PolicyDecision, Opportunity, BudgetPlan, LedgerRecord, SpendRequest, EvidenceRecord, ExperimentReview, etc.).
  - [x] Define enums (risk levels, decision states, action categories, blocked categories).
  - [x] Define error model (error_code, message, recoverable, details, safe_for_user).
  - [x] Add unit tests for schema validation using example JSON.

Reference: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md

## Phase 1 — Safety and state foundation

- [ ] Implement ledger_skill
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/ledger_skill/TODO.md
  - [ ] Create SQLite schema and migrations.
  - [ ] Implement append-oriented and tamper-evident ledger.
  - [ ] Add idempotency keys and duplicate prevention.
  - [ ] Add unit and integration tests.
- [ ] Implement moneybot_policy_guard
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/moneybot_policy_guard/TODO.md
  - [ ] Implement deterministic rule taxonomy and risk labels.
  - [ ] Implement allow/block/needs_review logic.
  - [ ] Integrate with ledger_skill for policy decision records.
  - [ ] Add unit and integration tests.
- [ ] Implement receipt_and_evidence_archiver
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/receipt_and_evidence_archiver/TODO.md
  - [ ] Implement local file storage layout.
  - [ ] Implement SHA-256 hashing and integrity checks.
  - [ ] Integrate with ledger_skill for evidence records.
  - [ ] Add unit and integration tests.

## Phase 2 — Research and decision skills

- [ ] Implement tos_legal_checker
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/tos_legal_checker/TODO.md
  - [ ] Implement rules/TOS extraction from fixtures.
  - [ ] Implement deterministic risk checks.
  - [ ] Implement legal-risk heuristics.
  - [ ] Integrate with moneybot_policy_guard and ledger_skill.
  - [ ] Add unit and integration tests.
- [ ] Implement budget_and_roi_planner
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/budget_and_roi_planner/TODO.md
  - [ ] Implement experiment budget and ROI calculations.
  - [ ] Implement decision rules (reject/simulate/execute_request/human_review).
  - [ ] Integrate with ledger_skill and wallet_governor_client.
  - [ ] Add unit and integration tests.
- [ ] Implement opportunity_scout
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/opportunity_scout/TODO.md
  - [ ] Define source categories and risk pre-filters.
  - [ ] Implement opportunity extraction, deduplication, and scoring.
  - [ ] Integrate with tos_legal_checker and ledger_skill.
  - [ ] Add unit and integration tests.

## Phase 3 — Execution-adjacent skills

- [ ] Implement email_drafter
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/email_drafter/TODO.md
  - [ ] Implement draft-only templates.
  - [ ] Implement anti-spam/deception checks.
  - [ ] Integrate with ledger_skill and receipt_and_evidence_archiver.
  - [ ] Add unit and integration tests.
- [ ] Implement wallet_governor_service
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/plugins/wallet_governor_service_TODO.md
  - [ ] Implement HTTP API endpoints (health, balance, quote-spend, send-small-payment, daily-limits).
  - [ ] Integrate with Bitcoin Core wallet locally.
  - [ ] Enforce spend limits, policy IDs, budget IDs, ledger pre-write.
  - [ ] Add unit and integration tests.
- [ ] Implement wallet_governor_client
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/wallet_governor_client/TODO.md
  - [ ] Implement HTTP client calls to wallet_governor_service.
  - [ ] Enforce client-side preflight checks.
  - [ ] Integrate with ledger_skill and receipt_and_evidence_archiver.
  - [ ] Add unit and integration tests.
- [ ] Implement experiment_reviewer
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/experiment_reviewer/TODO.md
  - [ ] Implement metrics calculation and decision rules.
  - [ ] Implement feedback loop for opportunity_scout, policy_guard, budget_and_roi_planner.
  - [ ] Integrate with ledger_skill and receipt_and_evidence_archiver.
  - [ ] Add unit and integration tests.

## Phase 4 — Integration pipeline

- [ ] Implement end-to-end dry-run workflow
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md
  - [ ] opportunity_scout finds candidates.
  - [ ] tos_legal_checker evaluates candidate.
  - [ ] moneybot_policy_guard approves/blocks.
  - [ ] budget_and_roi_planner creates experiment plan.
  - [ ] ledger_skill records plan.
  - [ ] email_drafter drafts required message.
  - [ ] receipt_and_evidence_archiver stores evidence.
  - [ ] experiment_reviewer reviews simulated outcome.
- [ ] Implement limited spend workflow with wallet_governor_service
  - [ ] Require ledger pre-write and policy/budget IDs.
  - [ ] Add integration tests (fake wallet-governor responses).
  - [ ] Test allowed tiny payment.
  - [ ] Test blocked over-limit payment.
  - [ ] Test blocked prohibited category payment.
  - [ ] Test missing ledger pre-write.

## Phase 5 — Configuration and deployment

- [ ] Add moneybot.yaml configuration
  - [ ] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md
  - [ ] Max spend limits.
  - [ ] Blocked categories.
  - [ ] Evidence archive path.
  - [ ] SQLite database path.
  - [ ] Wallet-governor URL.
  - [ ] Email mode (draft_only by default).
- [ ] Add safe defaults and startup validation
  - [ ] Default wallet spending disabled.
  - [ ] Default email sending disabled.
  - [ ] Default browser purchasing/form-submit disabled.
  - [ ] Default unknown action category to needs_review.
  - [ ] Fail closed if ledger DB unavailable.
  - [ ] Fail closed if policy config missing.
  - [ ] Fail closed if wallet-governor limits cannot be fetched.
- [ ] Add runbook documentation
  - [ ] How to run tests.
  - [ ] How to run a dry-run mission.
  - [ ] How to enable wallet spending.
  - [ ] How to disable wallet spending immediately.

## Phase 6 — Acceptance criteria

- [ ] No skill can send money directly.
- [ ] No skill can access private keys, seed phrases, wallet backups, or wallet passphrases.
- [ ] No skill can approve its own prohibited-category action.
- [ ] Every spend requires a policy decision, budget plan, ledger entry, and wallet-governor approval.
- [ ] Every opportunity has an evidence trail.
- [ ] Every external message is either draft-only or rate-limited through a governor.
- [ ] All unit tests pass offline.
- [ ] Integration tests prove blocked actions fail closed.
- [ ] The bot can complete a full no-money dry run from opportunity discovery to experiment review.

Reference: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md
