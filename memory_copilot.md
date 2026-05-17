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