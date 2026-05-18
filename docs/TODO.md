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
  - [x] Define common Pydantic models.
  - [x] Define enums.
  - [x] Define error model.
  - [x] Add unit tests for schema validation using example JSON.

Reference: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md

## Phase 1 — Safety and state foundation

- [x] Implement ledger_skill
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/ledger_skill/TODO.md
  - [x] Create SQLite schema and migrations.
  - [x] Implement append-oriented and tamper-evident ledger.
  - [x] Add idempotency keys and duplicate prevention.
  - [x] Add unit and integration tests.
- [x] Implement moneybot_policy_guard
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/moneybot_policy_guard/TODO.md
  - [x] Implement deterministic rule taxonomy and risk labels.
  - [x] Implement allow/block/needs_review logic.
  - [x] Integrate with ledger_skill for policy decision records.
  - [x] Add unit and integration tests.
- [x] Implement receipt_and_evidence_archiver
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/receipt_and_evidence_archiver/TODO.md
  - [x] Implement local file storage layout.
  - [x] Implement SHA-256 hashing and integrity checks.
  - [x] Integrate with ledger_skill for evidence records.
  - [x] Add unit and integration tests.

## Phase 2 — Research and decision skills

- [x] Implement tos_legal_checker
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/tos_legal_checker/TODO.md
  - [x] Implement rules/TOS extraction from fixtures.
  - [x] Implement deterministic risk checks.
  - [x] Implement legal-risk heuristics.
  - [x] Integrate with moneybot_policy_guard and ledger_skill.
  - [x] Add unit and integration tests.
- [x] Implement budget_and_roi_planner
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/budget_and_roi_planner/TODO.md
  - [x] Implement experiment budget and ROI calculations.
  - [x] Implement decision rules (reject/simulate/execute_request/human_review).
  - [x] Integrate with ledger_skill and wallet_governor_client.
  - [x] Add unit and integration tests.
- [x] Implement opportunity_scout
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/opportunity_scout/TODO.md
  - [x] Define source categories and risk pre-filters.
  - [x] Implement opportunity extraction, deduplication, and scoring.
  - [x] Integrate with tos_legal_checker and ledger_skill.
  - [x] Add unit and integration tests.

## Phase 3 — Execution-adjacent skills

- [x] Implement email_drafter
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/email_drafter/TODO.md
  - [x] Implement draft-only templates.
  - [x] Implement anti-spam/deception checks.
  - [x] Integrate with ledger_skill and receipt_and_evidence_archiver.
  - [x] Add unit and integration tests.
- [x] Implement wallet_governor_service
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/plugins/wallet_governor_service_TODO.md
  - [x] Implement HTTP API endpoints (health, balance, quote-spend, send-small-payment, daily-limits).
  - [x] Integrate with Bitcoin Core wallet locally.
  - [x] Enforce spend limits, policy IDs, budget IDs, ledger pre-write.
  - [x] Add unit and integration tests.
- [x] Implement wallet_governor_client
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/wallet_governor_client/TODO.md
  - [x] Implement HTTP client calls to wallet_governor_service.
  - [x] Enforce client-side preflight checks.
  - [x] Integrate with ledger_skill and receipt_and_evidence_archiver.
  - [x] Add unit and integration tests.
- [x] Implement experiment_reviewer
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/skills/experiment_reviewer/TODO.md
  - [x] Implement metrics calculation and decision rules.
  - [x] Implement feedback loop for opportunity_scout, policy_guard, budget_and_roi_planner.
  - [x] Integrate with ledger_skill and receipt_and_evidence_archiver.
  - [x] Add unit and integration tests.

## Phase 4 — Integration pipeline

- [x] Implement end-to-end dry-run workflow
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md
  - [x] opportunity_scout finds candidates.
  - [x] tos_legal_checker evaluates candidate.
  - [x] moneybot_policy_guard approves/blocks.
  - [x] budget_and_roi_planner creates experiment plan.
  - [x] ledger_skill records plan.
  - [x] email_drafter drafts required message.
  - [x] receipt_and_evidence_archiver stores evidence.
  - [x] experiment_reviewer reviews simulated outcome.
- [ ] Implement limited spend workflow with wallet_governor_service
  - [ ] Require ledger pre-write and policy/budget IDs.
  - [ ] Add integration tests (fake wallet-governor responses).
  - [ ] Test allowed tiny payment.
  - [ ] Test blocked over-limit payment.
  - [ ] Test blocked prohibited category payment.
  - [ ] Test missing ledger pre-write.

## Phase 5 — Configuration and deployment

- [x] Add moneybot.yaml configuration
  - [x] See: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md
  - [x] Max spend limits.
  - [x] Blocked categories.
  - [x] Evidence archive path.
  - [x] SQLite database path.
  - [x] Wallet-governor URL.
  - [x] Email mode (draft_only by default).
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

- [x] No skill can send money directly.
- [x] No skill can access private keys, seed phrases, wallet backups, or wallet passphrases.
- [x] No skill can approve its own prohibited-category action.
- [x] Every spend requires a policy decision, budget plan, ledger entry, and wallet-governor approval.
- [x] Every opportunity has an evidence trail.
- [x] Every external message is either draft-only or rate-limited through a governor.
- [x] All unit tests pass offline.
- [ ] Integration tests prove blocked actions fail closed.
- [ ] The bot can complete a full no-money dry run from opportunity discovery to experiment review.

Reference: docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/MASTER_IMPLEMENTATION_TODO.md
