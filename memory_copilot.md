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

## 2026-05-18T08:46:02Z - GPT-5.4 - Added P3 browser and email governors
- Implemented disabled-by-default `email_governor` and `browser_governor` plugin services instead of enabling live browser automation or unrestricted email sending.
- The email governor now enforces bot-owned sender allowlists, daily/domain/thread limits, policy approval, draft prewrite checks, outbound evidence archival, and deterministic inbound reply classification for opt-outs and complaints.
- The browser governor now enforces bot-owned profile IDs, blocks personal-account/KYC/CAPTCHA/bot-evasion/mass-signup/scraping flows, requires wallet-governor linkage for purchase actions, and records before/after browser evidence around governed actions.
- The repository passes full `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with 157 passing tests after the P3 work.

## 2026-05-18T08:54:23Z - GPT-5.4 - Added unit test coverage follow-up tracker
- Created `docs/UNIT_TEST1_TODO.md` as the next unit-test planning document after reviewing current coverage gaps.
- The follow-up plan prioritizes safety-critical coverage for `wallet_governor_service`, `wallet_governor_service` backend failures, `email_governor`, and deterministic branching in email templates/compliance and experiment review decisions.
- The new TODO also captures secondary coverage work for browser governor, wallet HTTP/client edge cases, config/factory validators, shared fixtures, and final acceptance criteria for the next testing pass.

## 2026-05-18T09:13:25Z - GPT-5.4 - Completed UNIT_TEST1 targeted coverage pass
- Implemented the planned UNIT_TEST1 coverage expansion across wallet governor service/backend, email governor, email drafter templates/compliance/models, experiment reviewer decisions, wallet HTTP/client validation, browser governor, config/base validators, and orchestration factory wiring.
- Added 43 new passing tests, bringing the suite to 235 passing tests and raising total repository coverage to 95%, with the targeted safety-critical modules now mostly at 94-99% coverage.
- Updated `docs/UNIT_TEST1_TODO.md` to mark the planned P0/P1/P2 targets complete and explicitly deferred only the lower-priority secondary backlog and broad shared-fixture refactor items to avoid unnecessary churn.

## 2026-05-18T09:30:10Z - GPT-5.4 - Added integration test follow-up tracker
- Created `docs/INT_TEST1_TODO.md` as the next integration-test planning document.
- The new tracker prioritizes fail-closed workflow gate coverage, wallet client-to-local-HTTP-wrapper integration, and governed email send/reply integration before secondary browser, review-feedback, linkage, and idempotency scenarios.
- The plan keeps the integration scope aligned with the project’s safety model by requiring offline, deterministic tests that exercise real local boundaries without live email, live Bitcoin Core, or browser automation.

## 2026-05-18T09:56:57Z - GPT-5.4 - Completed INT_TEST1 integration pass
- Finished the INT_TEST1 integration-test implementation across workflow fail-closed gates, the real wallet HTTP wrapper boundary, governed email flows, browser governor prepare/complete flows, review-feedback scenarios, ledger/evidence linkage checks, replay behavior, and local-only boundary regressions.
- Added offline integration helpers under `tests/integration/helpers.py`, new browser/email/wallet/workflow integration coverage, and deterministic replay behavior for governed email sends and browser actions so repeated requests do not create duplicate success artifacts.
- The repository now passes `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with 272 passing tests, and `docs/INT_TEST1_TODO.md` is complete.

## 2026-05-20T21:49:23Z - GPT-5.4 - Reviewed Code Review 2 spec and TODO
- Read `docs/CODE_REVIEW2_SPEC.md` and `docs/CODE_REVIEW2_TODO.md` to prepare for the next remediation pass focused on fail-closed wallet authorization, request/ledger mismatch rejection, durable failure handling, budget precedence, evidence validation, ledger spend-summary APIs, and stale documentation cleanup.
- The main design choice clarified with the user is that if a wallet send succeeds but the post-send lock step fails, the service should return success with a warning and record review/audit state rather than pretending the transaction failed.

## 2026-05-20T22:11:39Z - GPT-5.4 - Completed Code Review 2 remediation pass
- Finished the `docs/CODE_REVIEW2_TODO.md` implementation pass across wallet authorization, budget precedence and reference validation, evidence archive hardening, ledger spend summaries, orchestration/policy alignment, and stale review-doc cleanup.
- The wallet-governor service now requires executable policy metadata, exact request/ledger agreement, verified evidence files under a configured archive root, and structured handling for quote, unlock, send, and lock failures; post-send lock failures return success with a warning and an audit event.
- Added regression coverage for the new wallet failure paths, evidence hash/path checks, budget precedence and missing references, strict evidence-type and content-size validation, ledger spend summary APIs, and review-doc wording, bringing the suite to 296 passing tests with Ruff and mypy clean.

## 2026-05-20T23:01:58Z - GPT-5.4 - Completed Code Review 3 remediation pass
- Finished the `docs/CODE_REVIEW3_TODO.md` implementation pass across real BTC address validation, network-aware wallet safety, destination blocklisting, client quote fail-closed handling, explicit backend balance-failure auditing, spend-evidence type allowlisting, and exact satoshi accounting.
- Added a centralized shared Bitcoin validator used by the wallet service, wallet client preflight, and Bitcoin Core backend send preflight, with regtest constrained to explicit `bcrt1...` addresses and regression coverage for malformed, checksum-bad, mixed-case, blocked, and network-mismatched destinations.
- Added exact `amount_sats` and `fee_sats` storage plus integer-based ledger aggregation, review3 regression tests, and the review-fix docs; the repository now passes `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with 326 passing tests.

## 2026-05-21T03:56:21Z - GPT-5.4 - Added new skills implementation tracker
- Created `docs/SKILLS1_TODO.md` as a comprehensive first-party roadmap for the next wave of bounded MoneyBot skills.
- The tracker prioritizes `account_eligibility_checker`, `terms_change_monitor`, `submission_package_builder`, and `revenue_reconciler` first, then adds supporting skills for counterparty risk, duplicate detection, queue planning, deliverable validation, payout follow-up planning, and strategy summarization.
- The document keeps the scope aligned with the project’s safety model by requiring typed contracts, fail-closed behavior, ledger/evidence linkage, and no direct wallet-send, email-send, or browser-submit authority in the new skills.

## 2026-05-21T03:59:09Z - GPT-5.4 - Added new plugins implementation tracker
- Created `docs/PLUGINS1_TODO.md` as a comprehensive first-party roadmap for the next plugin/service wave that supports the new skills without expanding unsafe authority.
- The tracker prioritizes `operator_profile_store`, `rules_snapshot_gateway`, `wallet_observer_plugin`, and `inbox_observer_plugin`, then adds bounded local plugins for opportunity indexing, artifact rendering, deadline scheduling, download quarantine, counterparty snapshots, and metrics export.
- The document keeps plugin scope aligned with the project architecture by requiring localhost/read-only boundaries where appropriate, typed contracts, allowlists, fail-closed behavior, and ledger/evidence linkage rather than direct wallet-send, email-send, or unrestricted browser/shell power.

## 2026-05-21T04:28:39Z - GPT-5.4 - Completed SKILLS1 implementation pass
- Finished the `docs/SKILLS1_TODO.md` implementation pass across ten first-party skills: eligibility gating, terms monitoring, submission packaging, revenue reconciliation, counterparty profiling, duplicate detection, queue planning, deliverable validation, payout follow-up planning, and strategy summarization.
- Wired the new skills into orchestration and integration helpers with durable ledger/evidence linkage, added the supporting unit and integration coverage, and updated `docs/SKILLS1_TODO.md` plus `docs/TODO.md` to reflect the completed skill wave.
- The repository now passes `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with 381 passing tests at the end of this pass.

## 2026-05-21T05:34:37Z - GPT-5.4 - Completed PLUGINS1 Phase B
- Implemented and validated the second plugin wave from `docs/PLUGINS1_TODO.md`: `opportunity_index_plugin`, `artifact_renderer_plugin`, `deadline_scheduler_plugin`, and `download_quarantine_plugin`.
- Added typed models, plugin docs, and unit/integration coverage for deterministic similarity indexing, bounded local artifact rendering, fail-closed deadline scheduling, and quarantined download promotion into the evidence archive.
- Updated the PLUGINS1 tracker to mark all Phase B tasks complete, and the repository now passes `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with 436 passing tests.

## 2026-05-21T05:47:51Z - GPT-5.4 - Completed the full PLUGINS1 wave
- Implemented the final PLUGINS1 plugins `counterparty_snapshot_plugin` and `metrics_export_plugin`, then closed the remaining documentation and tracker work for the full first-party plugin wave.
- The plugin inventory is now documented in the architecture/spec docs, `docs/PLUGINS1_TODO.md` is fully checked off, and `docs/TODO.md` now records the completed PLUGINS1 wave alongside SKILLS1.
- The repository passes `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with 448 passing tests at the end of the full plugin implementation pass.

## 2026-05-21T05:58:52Z - GPT-5.4 - Current unit coverage hotspots
- A fresh coverage run after the full PLUGINS1 pass shows the main remaining branch-heavy unit-test gaps are `account_eligibility_checker/runner.py` (70%), `duplicate_opportunity_detector/runner.py` (73%), `opportunity_index_plugin/service.py` (76%), `metrics_export_plugin/service.py` (78%), and `counterparty_snapshot_plugin/service.py` (83%).
- Lower-priority but still worthwhile follow-ups include `artifact_renderer_plugin/service.py` (82%), `download_quarantine_plugin/service.py` (84%), `inbox_observer_plugin/service.py` (87%), and `terms_change_monitor/runner.py` (86%).

## 2026-05-21T05:58:52Z - GPT-5.4 - Added UNIT_TEST2 follow-up tracker
- Created `docs/UNIT_TEST2_TODO.md` as the next unit-test planning document after the post-PLUGINS1 coverage review.
- The new tracker prioritizes branch-heavy coverage for `account_eligibility_checker`, `metrics_export_plugin`, `opportunity_index_plugin`, `duplicate_opportunity_detector`, and `counterparty_snapshot_plugin`, with secondary follow-ups for renderer/quarantine/inbox/terms-monitor edge cases.

## 2026-05-21T06:19:52Z - GPT-5.4 - Added INT_TEST2 integration follow-up tracker
- Created `docs/INT_TEST2_TODO.md` as the next integration-test planning document after reviewing the remaining cross-skill and cross-plugin gaps.
- The new tracker prioritizes eligibility-gated workflow stops, rules-change recheck propagation, submission package to render/archive linkage, quarantine promotion boundaries, payout reconciliation loops, counterparty due-diligence flows, realistic metrics export coverage, and replay/idempotency checks.

## 2026-05-21T06:17:32Z - GPT-5.4 - Completed UNIT_TEST2 targeted coverage pass
- Finished the `docs/UNIT_TEST2_TODO.md` implementation pass across the planned hotspot modules and secondary edge-case follow-ups, including new direct branch tests for eligibility gating, duplicate matching, opportunity indexing, metrics export, counterparty snapshots, artifact rendering, download quarantine, inbox observation, and terms-change monitoring.
- Tightened one coupled bug uncovered by the new tests in `duplicate_opportunity_detector` by replacing lexicographic confidence escalation with an explicit severity ordering, keeping duplicate decisions deterministic.
- The repository now passes `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, `uv run --python 3.11 pytest`, and a follow-up coverage run at 95% total coverage; the targeted modules now report 100%, 100%, 98%, 97%, 96%, 99%, 98%, 87%, and 94% coverage respectively for the planned UNIT_TEST2 set.

## 2026-05-21T06:44:14Z - GPT-5.4 - Completed INT_TEST2 integration pass
- Finished the `docs/INT_TEST2_TODO.md` implementation pass by adding the Phase C integration coverage for realistic metrics exports, replay/idempotency of packaging and render flows, repeated terms-change and reconciliation requests, and repeated bounded export requests.
- Added reusable integration helpers for deterministic operator profiles, rules snapshot pairs, submission-template fixtures, and realistic mixed ledger history seeding, and fixed `metrics_export_plugin` so experiment-review exports resolve the underlying opportunity ID from integrated review payloads.
- The repository now passes `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with 575 passing tests, and `docs/INT_TEST2_TODO.md` is fully checked off.

## 2026-05-21T07:00:50Z - GPT-5.4 - Added bounded Playwright Firefox browser execution
- Extended `browser_governor` with a disabled-by-default Playwright+Firefox execution path that keeps browser control behind the existing governor boundary instead of exposing it to a skill directly.
- The new execution flow uses explicit host allowlists, bot-owned profile directories, typed bounded steps (`fill`, `click`, `wait_for_text`), replay-safe audit records, and archived before/after page text plus HTML snapshots.
- Added the Playwright dependency, config validation, README operator guidance for `playwright install firefox`, and unit coverage for successful execution, replay, allowlist rejection, and backend-failure handling; the full repository now passes `ruff`, `mypy`, and `pytest` with 582 passing tests.

## 2026-05-21T08:55:28Z - GPT-5.4 - Added Brave Search plugin
- Implemented a disabled-by-default `brave_search_plugin` for hosted web search using the Brave Search API instead of self-hosted search infrastructure.
- The plugin uses a configurable Brave API URL, an environment-variable credential (`BRAVE_SEARCH_API_KEY` by default), bounded result counts, archived raw response snapshots, ledger-linked `web_search` records, and read-only health reporting that surfaces missing credentials safely.
- Updated shared config/types/plugin exports, the architecture and README docs, and unit coverage for successful queries, disabled/missing-key behavior, transport failures, and malformed payloads; the repository now passes `ruff`, `mypy`, and `pytest` with 591 passing tests.

## 2026-05-21T20:32:50Z - GPT-5.4 - Added news search mode to Brave Search plugin
- Extended `brave_search_plugin` with a bounded `search_news()` path so MoneyBot can use Brave web search for current-events lookups without introducing a separate news API dependency yet.
- The news mode adds a dedicated request shape with recency and optional source-domain filters, separate `max_news_results` and `default_news_freshness` config, distinct audit/evidence labeling, and normalized result metadata that marks the query mode as `news`.
- Added unit coverage for news defaults, source-domain query shaping, and result-count enforcement; the full repository now passes `ruff`, `mypy`, and `pytest` with 593 passing tests.

## 2026-05-21T20:52:53Z - GPT-5.4 - Added Wikipedia research plugin
- Implemented a disabled-by-default `wikipedia_research_plugin` so MoneyBot can do bounded read-only research against Wikipedia without falling back to general web browsing for encyclopedia-style lookups.
- The plugin supports bounded article search through the MediaWiki search API and bounded page-summary fetches through the Wikipedia REST summary endpoint, with Wikipedia-only endpoint configuration, archived raw response snapshots, and ledger-linked `wikipedia_research` records.
- Added shared config/types/plugin exports plus unit coverage for search, summary fetches, disabled-mode handling, malformed payloads, and transport failures; the full repository now passes `ruff`, `mypy`, and `pytest` with 600 passing tests.

## 2026-05-21T21:14:26Z - GPT-5.4 - Published Wikipedia research plugin changes
- Committed the validated Wikipedia research plugin batch, including the shared config/type/export wiring, README and architecture updates, and the new unit coverage for bounded Wikipedia search and page-summary fetches.
- Pushed the updated `copilot` branch to GitHub so it now includes both the earlier Brave news-search commit and the Wikipedia research plugin commit.

## 2026-05-21T21:20:51Z - GPT-5.4 - Added arXiv research plugin
- Implemented a disabled-by-default `arxiv_research_plugin` so MoneyBot can do bounded research-paper discovery and paper lookups against arXiv through a read-only plugin boundary.
- The plugin supports bounded search queries plus direct paper lookup by arXiv ID, normalizes Atom feed results into paper metadata and clipped abstracts, archives raw XML response snapshots, and records ledger-linked `arxiv_research` entries.
- Added shared config/types/plugin exports, README and architecture updates, and unit coverage for search, paper lookup, disabled-mode handling, malformed XML payloads, and transport failures; the full repository now passes `ruff`, `mypy`, and `pytest` with 607 passing tests.

## 2026-05-21T21:29:55Z - GPT-5.4 - Added OpenAlex research plugin
- Implemented a disabled-by-default `openalex_research_plugin` so MoneyBot can do bounded scholarly-work discovery and work lookups against OpenAlex through a read-only plugin boundary.
- The plugin supports bounded works search plus direct work lookup, normalizes OpenAlex results into paper metadata with clipped reconstructed abstracts, archives raw JSON response snapshots, and records ledger-linked `openalex_research` entries.
- Added shared config/types/plugin exports, README and architecture updates, and unit coverage for search, work lookup, disabled-mode handling, missing API keys, malformed payloads, and transport failures; the full repository now passes `ruff`, `mypy`, and `pytest` with 615 passing tests.

## 2026-05-21T21:40:37Z - GPT-5.4 - Added combined biomedical research plugin
- Implemented a disabled-by-default `biomedical_research_plugin` so MoneyBot can do bounded biomedical paper search and paper lookups through a single read-only plugin boundary that supports both PubMed and Europe PMC.
- The plugin supports provider-selected search and paper lookup flows, normalizes PubMed XML and Europe PMC JSON into shared paper metadata with clipped abstracts, archives raw provider responses, and records ledger-linked `biomedical_research` entries.
- Added shared config/types/plugin exports, README and architecture updates, and unit coverage for PubMed search and paper lookup, Europe PMC search, disabled-mode handling, malformed payloads, and transport failures; the full repository now passes `ruff`, `mypy`, and `pytest` with 623 passing tests.

## 2026-05-21T21:55:08Z - GPT-5.4 - Published research plugin batch
- Committed the validated research-plugin batch covering `arxiv_research_plugin`, `openalex_research_plugin`, and the combined `biomedical_research_plugin`, along with the shared config/type/export wiring, README and architecture updates, and new unit coverage.
- Pushed the updated `copilot` branch to GitHub so it now includes the post-Wikipedia research plugin expansion for arXiv, OpenAlex, PubMed, and Europe PMC.

## 2026-05-21T22:04:16Z - GPT-5.4 - Added Mastodon discovery plugin
- Implemented a disabled-by-default `mastodon_discovery_plugin` so MoneyBot can do bounded public timeline sampling against one configured Mastodon instance through a read-only plugin boundary.
- The plugin supports optional bearer-token auth for instances that disable unauthenticated public preview, normalizes sampled statuses into text/author/tag/link summaries, archives raw timeline responses, and records ledger-linked `mastodon_discovery` entries.
- Added shared config/types/plugin exports, README and architecture updates, and unit coverage for bounded sampling, optional auth, disabled-mode handling, malformed payloads, and transport failures; the full repository now passes `ruff`, `mypy`, and `pytest` with 631 passing tests.

## 2026-05-21T22:13:47Z - GPT-5.4 - Added Bluesky discovery plugin
- Implemented a disabled-by-default `bluesky_discovery_plugin` so MoneyBot can do bounded public feed sampling through the public Bluesky AppView API without adding authenticated social-account access.
- The plugin supports a configured or per-request feed URI, normalizes sampled posts into text/author/link/label summaries, archives raw feed responses, and records ledger-linked `bluesky_discovery` entries.
- Added shared config/types/plugin exports, README and architecture updates, and unit coverage for bounded sampling, default-feed fallback, disabled-mode handling, malformed payloads, and transport failures; the full repository now passes `ruff`, `mypy`, and `pytest` with 639 passing tests.

## 2026-05-21T22:18:05Z - GPT-5.4 - Published social discovery plugin batch
- Committed the validated discovery-plugin batch covering `mastodon_discovery_plugin` and `bluesky_discovery_plugin`, along with the shared config/type/export wiring, README and architecture updates, and unit coverage.
- Pushed the updated `copilot` branch to GitHub so it now includes bounded Mastodon public timeline sampling and Bluesky public feed sampling.

## 2026-05-21T22:26:16Z - GPT-5.4 - Added stock market data plugin
- Implemented a disabled-by-default `stock_market_data_plugin` so MoneyBot can do bounded read-only stock price lookups through Alpha Vantage without adding trading, screening, or execution behavior.
- The plugin supports single-symbol quote lookup plus recent daily OHLCV bars, archives raw Alpha Vantage responses, and records ledger-linked `stock_market_data` entries.
- Added shared config/types/plugin exports, README and architecture updates, and unit coverage for quote lookup, daily bars, disabled-mode handling, missing API keys, provider-rate-limit notes, and transport failures; the full repository now passes `ruff`, `mypy`, and `pytest` with 647 passing tests.

## 2026-05-22T00:55:16Z - GPT-5.4 - Published stock market data plugin
- Committed the validated `stock_market_data_plugin` batch, including the shared config/type/export wiring, README and architecture updates, and unit coverage for bounded Alpha Vantage quote and daily-bar lookups.
- Pushed the updated `copilot` branch to GitHub so it now includes the read-only stock market data plugin and the matching README documentation.

## 2026-05-22T01:02:12Z - GPT-5.4 - Added crypto market data plugin
- Implemented a disabled-by-default `crypto_market_data_plugin` so MoneyBot can do bounded read-only crypto market lookups through CoinGecko without adding trading, exchange, wallet, DeFi, NFT, or token-flow behavior.
- The plugin supports coin-ID-based spot-price lookup plus recent market-chart points, archives raw CoinGecko responses, and records ledger-linked `crypto_market_data` entries.
- Added shared config/types/plugin exports, README and architecture updates, and unit coverage for spot-price lookup, recent chart retrieval, disabled-mode handling, provider error payloads, malformed responses, and transport failures; the full repository now passes `ruff`, `mypy`, and `pytest` with 655 passing tests.

## 2026-05-22T01:55:17Z - GPT-5.4 - Added Kuzu rollout guide
- Added `docs/KUZU.md` with detailed instructions for adopting Kuzu as an internal graph memory module/service rather than as a plugin or canonical store.
- The guide clearly separates v1 from post-v1 scope, documents future dependency/configuration examples, recommends SQLite remain canonical, and lays out schema, projection, maintenance, provenance, and testing guidance for a later rollout.

## 2026-05-22T01:58:13Z - GPT-5.4 - Published crypto plugin and Kuzu guide
- Committed the validated `crypto_market_data_plugin` batch together with the new `docs/KUZU.md` rollout guide, including the shared config/type/export wiring, architecture and README updates, and unit coverage.
- Pushed the updated `copilot` branch to GitHub so it now includes the CoinGecko-backed crypto market data plugin and the detailed Kuzu adoption documentation.

## 2026-05-22T19:31:40Z - GPT-5.4 - Added inner voice plugin spec
- Added `docs/INNER_VOICE_SPEC.md` as a comprehensive specification for a governed inner-voice challenger plugin that critiques the main model's conclusions without becoming a second autonomous agent.
- The spec defines provider support for OpenAI, Ollama, and llama-server, structured input/output contracts, invocation points, safety rules, hosted-provider opt-in, ledger/evidence behavior, failure handling, and a phased rollout plan.

## 2026-05-22T19:36:11Z - GPT-5.4 - Expanded inner voice spec details
- Expanded `docs/INNER_VOICE_SPEC.md` to pin down implementation-defining details that were still open, including the runtime placement and persistence path, normalized provider request/response contracts, configuration edge rules, fixed schema enums, evidence truncation rules, archive redaction policy, failure persistence behavior, and deterministic stage interpretation rules.
- The spec now also defines usefulness metrics for rollout evaluation and narrows the remaining open questions to a small set of post-spec implementation choices rather than core architecture gaps.

## 2026-05-22T19:38:14Z - GPT-5.4 - Forbid LiteLLM for inner voice connectivity
- Updated `docs/INNER_VOICE_SPEC.md` to make the LLM connectivity model explicit: the inner voice plugin must use direct provider-specific adapters for OpenAI, Ollama, and llama-server rather than a generic LLM gateway or aggregation layer.
- The spec now explicitly forbids LiteLLM for inner voice provider access so request handling, credential flow, fallback behavior, and transport semantics remain directly auditable inside the repository.

## 2026-05-22T19:42:22Z - GPT-5.4 - Resolved more inner voice v1 decisions
- Updated `docs/INNER_VOICE_SPEC.md` so v1 does not assume or document a built-in default model; the operator must explicitly choose `model_name` when enabling the inner voice plugin.
- The spec now also recommends fixed-in-code per-stage prompt templates for v1 and explicitly allows multiple challenger passes for the same subject, with unique review IDs, pass indexes, and immutable linked review records.

## 2026-05-22T19:51:56Z - GPT-5.4 - Debate round limit should be configurable
- Recorded the requirement that any future OpenClaw-versus-Inner-Voice debate window should use a configurable maximum round count instead of a hard-coded limit.
- This will matter when the Arbiter/escalation design is specified, because orchestration should control when debate stops and escalation begins.

## 2026-05-22T19:56:00Z - GPT-5.4 - Added debate transcript logging to inner voice spec
- Extended `docs/INNER_VOICE_SPEC.md` with debate-specific logging requirements, including `max_debate_rounds`, transcript archival flags, an `INNER_VOICE_DEBATE` record type, debate session and turn schemas, transcript ordering rules, and linkage to later escalation or Arbiter records.
- The spec now explicitly says the operator should be able to inspect the actual exchanged debate dialogue round by round while clarifying that the stored transcript is the visible model-to-model dialogue, not hidden internal reasoning or inaccessible raw chain-of-thought.

## 2026-05-22T20:11:22Z - GPT-5.4 - Added Arbiter resolution spec
- Extended `docs/INNER_VOICE_SPEC.md` with a dedicated Arbiter design: the Arbiter is required rather than behind an enable flag, is invoked when max debate rounds are reached without agreement or when either debate participant requests arbitration, and may use a different provider/model than OpenClaw or the main inner voice.
- The spec now includes Arbiter config rules, request/result schemas, `ARBITER_REVIEW` persistence, audit linkage back to debate transcripts, failure behavior, and the v1 rule that one Arbiter pass produces the final LLM-level resolution for that debate session while still remaining subordinate to deterministic policy gates.

## 2026-05-22T20:14:43Z - GPT-5.4 - Added inner voice implementation TODO doc
- Added `docs/INNER_VOICE_TODO.md` as a comprehensive implementation tracker derived from `docs/INNER_VOICE_SPEC.md`, covering the inner voice plugin, bounded debate loop, debate transcript persistence, required Arbiter escalation, provider adapters, shared contracts, prompt building, ledger/archive wiring, tests, metrics, and rollout tasks.
- The new TODO doc breaks the work into detailed priorities, tasks, and subtasks so the feature can be implemented incrementally without reopening the core architecture decisions already captured in the spec.
## 2026-05-22T20:37:34Z - GPT-5.4 - Inner voice implementation slice is green
- Implemented the first full inner-voice package slice under `src/openclaw_moneybot/plugins/inner_voice_plugin/`, including typed review/debate/Arbiter models, direct provider adapters for OpenAI/Ollama/llama-server, prompt builders, the review service, the Arbiter service, bounded debate coordination, archive/ledger persistence, and factory wiring.
- Added shared config and type support for `inner_voice` and `arbiter`, plus unit/integration coverage in `tests/unit/test_inner_voice_plugin.py`, `tests/integration/test_inner_voice_integration.py`, `tests/unit/shared/test_config.py`, and `tests/unit/test_orchestration_factory.py`.
- The repository now passes full `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with the new inner-voice slice included.
- The main remaining design gap is workflow integration: `MoneyBotOrchestrator.run_dry_run()` has no existing OpenClaw main-model runtime to participate in live debate rounds, so deeper stage-triggered debate wiring needs an explicit orchestration decision rather than silently inventing one.
## 2026-05-22T19:40:35-07:00 - GPT-5.4 - Pushed inner voice review and debate phase commit d2df17a
- Committed and pushed `d2df17a` (`Implement inner voice review and debate phase`) on the `copilot` branch after the full repository passed `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest`.
- This phase added the inner voice plugin package, Arbiter service, bounded debate coordinator, shared config/type wiring, review-only workflow integration in `run_dry_run()`, updated operator docs, and initial TODO status tracking.
- The remaining unchecked tracker items are concentrated in follow-up hardening and polish areas such as prompt-size bounding, deeper sanitization/redaction modes, richer failure-object shaping, additional TODO status cleanup, and any future debate-driven spend/irreversible workflow behavior beyond the review-only dry-run integration.

## 2026-05-23T06:04:47Z - GPT-5.4 - Hardened inner voice prompt and provider handling
- Hardened the inner-voice and Arbiter runtime with bounded prompt construction, deterministic truncation markers, evidence ordering/deduplication, stale-evidence labeling, stronger secret redaction and hash modes, provider health checks, and more specific failure classification including `prompt_too_large`.
- Added prompt-size, stale-evidence, provider-unreachable, and prompt-too-large coverage in `tests/unit/test_inner_voice_plugin.py`, and updated `docs/INNER_VOICE_TODO.md` to mark the completed provider/model/prompt/service hardening items from this phase.
- The repository again passes full `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest`, now with 677 passing tests.

## 2026-05-23T06:18:52Z - GPT-5.4 - Hardened debate archival and required-stage handling
- Hardened the debate/runtime path so required inner-voice stages fail closed when not configured, debates emit audit events for start/completion/escalation/failure, transcript archival honors the raw-transcript and turn-metadata config flags, and debate summaries now carry linked review IDs plus Arbiter resolution notes.
- Added coverage for required-stage-missing wallet-path behavior, debate audit events, transcript placeholder archival, Arbiter failure request-summary archival, debate summary linkage, and prompt-size metrics updates in `tests/integration/test_workflow.py` and `tests/unit/test_inner_voice_plugin.py`.
- Updated `docs/INNER_VOICE_TODO.md` and `docs/OPENCLAW_MONEYBOT_ARCHITECTURE.md` to reflect the completed debate/orchestration/Arbiter archival work, and the repository now passes full `uv run --python 3.11 ruff check .`, `uv run --python 3.11 mypy .`, and `uv run --python 3.11 pytest` with 680 passing tests.
## 2026-05-23T06:28:18Z - GPT-5.4 - Added deterministic disagreement interpretation
- Added `ModelDisagreementInterpretation` plus `MoneyBotOrchestrator.interpret_model_disagreement(...)` so debate and Arbiter outcomes map back into deterministic workflow statuses without allowing LLM output to outrank deterministic gates.
- Added workflow integration coverage for spend-path debate follow-up handling, irreversible-action debate blocking, and deterministic policy outranking an Arbiter `adopt_openclaw` result.
- Updated `docs/INNER_VOICE_TODO.md` to mark the newly completed deterministic-interpretation and workflow-integration items from this phase.
## 2026-05-23T06:45:32Z - GPT-5.4 - Hardened provider compatibility and interpretation rules
- Added explicit OpenAI JSON-contract rejection for clearly incompatible endpoint/model configurations and documented the llama-server adapter's minimal content-part joining behavior before strict JSON validation.
- Tightened orchestration's inner-voice interpretation matrix so spend-path budget reviews now route low-confidence or follow-up-gated results to `needs_review`, and added integration coverage for both budget-stage spend gating and Arbiter `adopt_inner_voice` interpretation.
- Updated `docs/INNER_VOICE_TODO.md` to mark the provider-compatibility and deterministic-interpretation items completed in this phase.
## 2026-05-23T06:53:50Z - GPT-5.4 - Added inner-voice diagnostics helpers
- Inner-voice and Arbiter failures now carry typed structured failure objects, and review/Arbiter `raw_response_summary` values are now stable typed provider-response summaries instead of ad hoc dicts.
- Added inner-voice observability helpers to persist computed metrics snapshots and to query persisted review, debate, and Arbiter records by subject, stage, and outcome through the ledger event stream.
- Updated `docs/INNER_VOICE_TODO.md` to mark the diagnostics/observability items completed in this phase.
## 2026-05-23T07:02:23Z - GPT-5.4 - Completed remaining inner-voice TODO items
- The final inner-voice phase added stage/subject relevance gating for debate requests, records `orchestrator_escalation` end states plus a dedicated audit event, and adds a `MoneyBotOrchestrator.settle_model_disagreement(...)` helper that fails closed to `needs_review` on required execution-adjacent debate failures.
- `docs/INNER_VOICE_TODO.md` is now fully checked off, and the rollout notes in `docs/OPENCLAW_MONEYBOT_ARCHITECTURE.md` now document the selected high-risk default stages, transcript-capture default, usefulness/noise measurement expectation, and post-v1 follow-up items.
- Full repository validation passed again after these completion changes.
## 2026-05-23T07:25:42Z - GPT-5.4 - Added UNIT_TEST3 coverage tracker
- Added `docs/UNIT_TEST3_TODO.md`, a detailed unit-test follow-up tracker based on the latest 90% coverage review.
- The new tracker prioritizes browser governor backend safety branches, inner-voice provider adapters, research/discovery parser services, debate/workflow helper coverage, and a smaller validator/config sweep.
- The tracker also includes the required repo validation and coverage rerun steps for the eventual UNIT_TEST3 implementation pass.
## 2026-05-23T07:35:50Z - GPT-5.4 - Started UNIT_TEST3 phase one
- UNIT_TEST3 phase one is now green locally: added direct unit coverage for `browser_governor/backend.py` helper and execute-flow branches plus `inner_voice_plugin/providers.py` health, strict parsing, malformed-response, and adapter-factory behavior.
- `docs/UNIT_TEST3_TODO.md` now exists as the master tracker for this coverage pass, and sections 1-2 are marked complete.
- Full repository validation passed after the phase-one additions.
