## 2026-05-17T18:30:13Z - GPT-5.4 - Reviewed skill TODO documents
- Reviewed all markdown files under `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/`, including the master TODO, README, all nine skill TODOs, and the wallet governor and ledger API plugin TODOs.
- The docs consistently treat `ledger_skill`, `moneybot_policy_guard`, and `receipt_and_evidence_archiver` as the foundational control layer to implement before execution-adjacent skills.
- The recommended skill build order in the TODO package is: `ledger_skill`, `moneybot_policy_guard`, `receipt_and_evidence_archiver`, `tos_legal_checker`, `budget_and_roi_planner`, `opportunity_scout`, `email_drafter`, `wallet_governor_client`, `experiment_reviewer`.
- The implementation handoff docs assume Python with Pydantic v2 contracts, SQLite-backed local state, fixture-driven offline tests, and deterministic rule engines for safety-critical logic.
- Cross-cutting expectations repeated throughout the TODOs: fail closed on uncertainty, keep wallet access behind `wallet_governor_service`, require ledger prewrites before meaningful external actions, archive evidence aggressively, and preserve tamper-evident/idempotent audit records.
- Skill-specific themes:
  - `ledger_skill`: append-oriented SQLite ledger, tamper-evident hash chain, idempotency, accounting export, and strong linkage across opportunities, policy, spend, email, evidence, and reviews.
  - `moneybot_policy_guard`: deterministic taxonomy/rule engine with hard blocks first, `needs_review` for ambiguity, and structured policy records usable by downstream workflows.
  - `tos_legal_checker`: evidence-backed rules review that returns `proceed`, `reject`, or `human_review`, never treating missing or ambiguous rules as approval.
  - `budget_and_roi_planner`: bounded experiment planning requiring explicit max loss, fees, success metric, timebox, stop condition, and wallet/ledger handoff only when all gates pass.
  - `opportunity_scout`: research-only candidate discovery with deterministic scoring, dedupe, source evidence, and no power to spend, message, or submit.
  - `email_drafter`: draft-only v1 email generation with anti-spam, anti-deception, and ledger/evidence linkage.
  - `wallet_governor_client` and `wallet_governor_service`: strict separation from raw Bitcoin Core access, localhost-only/local service assumptions, hard spend limits, no `send_all`, and mandatory policy/budget/ledger references.
  - `receipt_and_evidence_archiver`: immutable local archive, SHA-256 hashing, metadata sidecars, secret redaction, and ledger-linked evidence manifests.
  - `experiment_reviewer`: deterministic experiment outcome review with feedback loops into scouting, policy, and budgeting.

## 2026-05-17T18:35:38Z - GPT-5.4 - Added master project TODO
- Created `docs/TODO.md` as the top-level project tracker for OpenClaw MoneyBot.
- The new master TODO organizes work into phases: repository/tooling foundation, shared contracts/config/errors, ledger, policy guard, evidence archive, TOS/legal checking, budget planning, opportunity scouting, draft-only email, wallet governor service, wallet governor client, experiment review, orchestration, and acceptance/operations.
- The document explicitly points back to the detailed skill and plugin TODO files under `docs/OPENCLAW_MONEYBOT_SKILLS_TODOS/` so there is a single project-management entry point plus deeper implementation checklists.
- The suggested first implementation slice remains: Python/tooling foundation -> shared contracts/config/errors -> `ledger_skill` -> `moneybot_policy_guard` -> `receipt_and_evidence_archiver`.

## 2026-05-17T18:58:49Z - GPT-5.4 - Completed phases 0 through 6
- Implemented and pushed the first six phases from `docs/TODO.md`: project/tooling foundation, shared contracts/config/errors, ledger foundation, deterministic policy guard, evidence archive, TOS/legal checker, and budget planner.
- The repository now has a working Python 3.11 + uv scaffold, shared Pydantic contracts and config loading, an SQLite ledger with tamper-evident event hashing, a deterministic policy gate, a local evidence archiver with redaction and ledger integration, an offline-first TOS/legal checker, and a bounded budget planner with wallet handoff generation.
- Each completed phase was followed by `ruff`, `mypy`, and `pytest`, and the changes were committed and pushed in phase-by-phase commits on the `copilot` branch.
- Remaining phases are still pending: opportunity scouting, draft-only email, wallet governor service, wallet governor client, experiment reviewer, optional local services, orchestration, and final acceptance/operations work.

## 2026-05-17T19:07:02Z - GPT-5.4 - Completed phases 7 and 8
- Implemented and pushed Phase 7 `opportunity_scout` with deterministic source parsing, candidate filtering, deduplication, ranking, and downstream TOS/legal handoff data.
- Implemented Phase 8 `email_drafter` as a strict draft-only skill with safe templates, compliance/risk checks, ledger email records, and archived draft bodies linked through the evidence system.
- The repository now passes full `ruff`, `mypy`, and `pytest` after phases 7 and 8, with 70 passing tests covering the new scout and email behavior.
- Next code phases are wallet governor service, wallet governor client, experiment reviewer, optional local services, and orchestration; manual acceptance work remains intentionally deferred for now.

## 2026-05-17T19:09:42Z - GPT-5.4 - Completed phase 9 wallet governor service
- Implemented a local-only `wallet_governor_service` plugin package with deterministic health, balance, limits, quote, and governed send operations backed by a fake wallet backend for tests.
- The service now enforces spend-enabled gating, supported-asset checks, single/daily/weekly USD caps, no-`send_all`, required purpose/counterparty/destination/reference fields, idempotent responses, and unlock-then-lock wallet handling around sends.
- Successful sends write both `SpendRequest` and `WalletTransactionRecord` entries to the ledger, keeping wallet activity inside the documented wallet boundary and preserving auditability.
- The repository passes full `ruff`, `mypy`, and `pytest` after adding the wallet governor service, bringing the automated test count to 78 passing tests.

## 2026-05-17T19:29:46Z - GPT-5.4 - Completed phases 10 through 14
- Implemented `wallet_governor_client` with localhost-only config enforcement, deterministic preflight checks, ledgered prewrites, archived service responses, and safe handling of sent, rejected, and error outcomes.
- Implemented `experiment_reviewer`, a narrow `ledger_api`, and the default orchestrated workflow under `src/openclaw_moneybot/orchestration/`, including a dry-run mission path and a tiny capped payment path backed by the fake wallet backend.
- Added integration coverage for one full dry-run workflow, one fail-closed wallet path, and one tiny capped payment path, plus extra config-default tests for disabled wallet spending and draft-only email mode.
- Updated `README.md` with operator instructions for `uv` setup, Ruff, mypy, pytest, config defaults, dry-run mission wiring, and wallet spending toggles. The repository now passes full `ruff`, `mypy`, and `pytest` with 104 passing tests.

## 2026-05-18T07:35:07Z - GPT-5.4 - External review follow-up notes
- Read `tmp/CODE_REVIEW1.md`, which compared this implementation against an OpenCode version and strongly recommended continuing from the Copilot codebase.
- The most important follow-up issues called out were wallet-path hardening items: make `wallet_governor_service` verify policy/budget/TOS/ledger/evidence independently, require TOS `proceed` instead of allowing `human_review` for autonomous spend, fix weekly spend SQL date arithmetic, and clarify client/service ownership of spend-request creation.
- Secondary follow-ups noted in the review were adding workspace allowlisting for archived file paths, tightening `PURCHASE` semantics in policy/orchestration, and eventually adding a real wallet backend and local HTTP wrapper only after the service boundary is hardened.

## 2026-05-18T08:28:12Z - GPT-5.4 - Completed CODE_REVIEW1 implementation pass
- Implemented the CODE_REVIEW1 hardening pass across wallet authorization, ledger accounting, policy/TOS/budget handoffs, evidence restrictions, email/reviewer safety, opportunity source adapters, and supporting docs.
- Fixed the orchestration regression so paid opportunities now use non-executable initial review semantics while real purchase execution still routes through the governed wallet path, restoring the dry-run, fail-closed, and tiny capped payment integration flows.
- Added the local FastAPI wallet-governor wrapper, the disabled-by-default Bitcoin Core backend skeleton, safety regression fixtures, and the review-fix documentation set; `docs/CODE_REVIEW1_TODO.md` now reflects the completed implementation items.
- The repository passes full `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with 145 passing tests at the end of this pass.