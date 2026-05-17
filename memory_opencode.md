## 2026-05-17T18:52:35Z - [local-llm] - Read project spec and architecture

- Read OPENCLAW_MONEYBOT_PROJECT_SPEC.md:
  - Purpose: constrained autonomous experiment-runner for legal money-making opportunities.
  - Local LLM only; no hosted APIs.
  - ~$100 BTC hot wallet on dedicated machine.
  - 9 core skills; each narrow and independently testable.
  - Strict policy + ledger + wallet governor constraints before any spend/send/submit.

- Read OPENCLAW_MONEYBOT_ARCHITECTURE.md:
  - Layered architecture: LLM → OpenClaw orchestration → skills → validators → governed plugins → ledger/archive/wallet.
  - Deterministic service boundaries are the enforcement layer, not prompts.
  - Key services: wallet_governor_service, ledger_api, email_governor, archive_store, browser_governor.
  - SQLite ledger is canonical source of truth.
  - Fail-closed rules: missing/ambiguous checks block actions.

- Key design principles to remember:
  - Never expose wallet secrets to LLM/skills.
  - Spend/send/submit must be gated by policy + ledger + wallet governor.
  - Use strict schemas; validate LLM JSON; fail closed on invalid JSON.
  - No direct bitcoin-cli or RPC access from bot; only wallet_governor_service.

## 2026-05-17T19:00:14Z - [local-llm] - Project tooling and quality constraints

- Use Python 3.11.
- Use uv for Python environment and dependency management.
- Lint: ruff; type-check: mypy; test: pytest.
- All lint/type/test warnings must be fixed, never ignored or silenced.

## 2026-05-17T19:14:51Z - [local-llm] - OpenClaw MoneyBot skills TODOs (high-level)

- Read all TODOs under OPENCLAW_MONEYBOT_SKILLS_TODOS.
- Tech stack:
  - Python 3.11.
  - Pydantic v2 for typed contracts.
  - SQLite for durable local state and tests.
  - Deterministic rule engines for safety-critical decisions.
  - No external commercial LLM APIs; local LLM only.
  - No direct wallet access (no bitcoin-cli, no RPC credentials, no private keys).

- Implementation phases:

  - Phase 0: Repo scaffolding
    - skills/ directory, one per skill.
    - pyproject.toml, Pydantic, pytest, ruff.
    - Test folder (SQLite temp DBs; fixture-based; no network).
    - Shared contracts (common models: MoneyBotAction, PolicyDecision, Opportunity, etc.).
    - Shared error model with structured fields.

  - Phase 1: Safety and state foundation
    - Implement ledger_skill first.
    - Implement moneybot_policy_guard second.
    - Implement evidence archiver before external execution.

  - Phase 2: Research and decision skills
    - tos_legal_checker
    - budget_and_roi_planner
    - opportunity_scout

  - Phase 3: Execution-adjacent skills
    - email_drafter (draft-only first)
    - wallet_governor_client (after wallet-governor service exists)
    - experiment_reviewer (last)

  - Phase 4: Integration pipeline
    - End-to-end dry-run workflow.
    - Limited spend workflow with wallet-governor.
    - Integration tests with fake wallet-governor responses.

  - Phase 5: Config and deployment
    - moneybot.yaml: limits, categories, ledger path, wallet-governor URL, email mode.
    - Safe defaults: spending disabled, email disabled, browser actions disabled.
    - Startup validation; fail closed on critical failures.
    - Runbook documentation.

  - Phase 6: Acceptance
    - No skill sends money directly.
    - No skill accesses private keys.
    - No self-approval of prohibited actions.
    - Every spend requires policy, budget, ledger, wallet-governor approval.
    - Offline unit tests pass; integration tests prove fail-closed behavior.

- Build order:
  - 1) ledger_skill
  - 2) moneybot_policy_guard
  - 3) receipt_and_evidence_archiver
  - 4) tos_legal_checker
  - 5) budget_and_roi_planner
  - 6) opportunity_scout
  - 7) email_drafter
  - 8) wallet_governor_client
  - 9) experiment_reviewer

- Plugins:
  - wallet_governor_service:
    - Local HTTP service owning Bitcoin Core wallet access.
    - Enforces spend limits, policy IDs, budget IDs, ledger pre-write.
    - Hard safety rules, no-key exposure.
  - ledger_api (optional):
    - Local API exposing SQLite ledger for audit data.
    - No arbitrary SQL; idempotency keys; hash chain preserved.

- Per-skill essence:

  - moneybot_policy_guard:
    - Deterministic rule-based allow/block/needs_review gate.
    - Prohibited categories (trading, gambling, spam, etc.) hard-block.
    - Requires policy decision ID for subsequent actions.

  - opportunity_scout:
    - Research-only, no wallet/email/send powers.
    - Produces OpportunityCandidate list with evidence and risk prechecks.
    - Candidates unverified until TOS/legal and policy checks.

  - tos_legal_checker:
    - Evaluates platform rules, legal risk, TOS compliance.
    - Fail closed on uncertainty.
    - Outputs proceed/reject/human_review with evidence and handoff to policy guard.

  - budget_and_roi_planner:
    - Converts vetted opportunity into experiment plan: max loss, expected ROI, success/stop metrics.
    - No wallet spend without policy and TOS approval.
    - Ledger-ready; deterministic math.

  - ledger_skill:
    - Append-oriented SQLite ledger: opportunities, policy decisions, TOS checks, budget plans, spends, BTC transactions, evidence, emails, reviews.
    - Tamper-evident event chain; idempotency; tax/accounting fields.

  - wallet_governor_client:
    - Talks only to wallet-governor service via HTTP.
    - Requires policy, budget, ledger IDs for any spend.
    - Fails closed on service unavailability or missing approvals.

  - email_drafter:
    - Draft-only in v1.
    - Templates for bounty/application/support/receipt/follow-up.
    - Strong anti-spam/deception rules; ties drafts to opportunities and ledger.

  - receipt_and_evidence_archiver:
    - Stores evidence files immutably with metadata and SHA-256 hashes.
    - Links evidence to opportunities/decisions via ledger.
    - Redacts secrets if accidentally captured.

  - experiment_reviewer:
    - Reviews experiments using ledger data, computes ROI/metrics.
    - Outputs continue/stop/retry/human_review decisions.
    - Feeds lessons back into opportunity scoring, policy, and budgeting.

## 2026-05-17T19:54:16Z - [local-llm] - Ralph Loop concept

- Ralph Loop (from Geoffrey Huntley) is an autonomous, goal-driven development pattern for vibe coding with AI.
- Core idea:
  - Define a goal, constraints, specs, and acceptance criteria.
  - Let an AI loop iteratively act, fail, learn, and adjust instead of hand-crafting every step.
- Ralph is a single autonomous loop:
  - One repo, one process, one task per cycle.
  - Engineer failure modes (tests, linting, type-checking, guardrails) so mistakes are visible and fixable.
- Developer role:
  - Program the loop via clear specs and context.
  - Watch the loop, detect failure domains, harden against repeated errors.
- Ralph Loop formalizes “vibe coding” into a systematic, repeatable workflow instead of ad-hoc prompting.
