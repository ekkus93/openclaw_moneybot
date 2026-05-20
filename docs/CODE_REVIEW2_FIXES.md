# CODE_REVIEW2_FIXES.md

# OpenClaw MoneyBot — Code Review 2 Fixes

## Summary

This pass completed the P0, P1, and P2 follow-up work from `docs/CODE_REVIEW2_TODO.md`.

Real spend remains disabled by default, the Bitcoin Core backend remains disabled by default, and the wallet path now fails closed on policy, request, evidence, and backend ambiguity.

## Fixed P0 issues

- Persisted executable policy action metadata through the shared contracts, policy guard, and ledger schema/repository.
- Tightened wallet-governor authorization so the incoming request must match the ledger spend request and the linked policy must approve the exact executable wallet action.
- Updated early and backend failure paths so spend request status transitions are durable and auditable.
- Applied destination validation to the quote path as well as the send path.
- Converted fee quote, unlock, send, and lock failures into structured governed outcomes with audit coverage and post-send lock warnings.

## Fixed P1 issues

- Enforced budget planner decision precedence: `REJECT > HUMAN_REVIEW > SIMULATE > EXECUTE_REQUEST`.
- Added graceful missing-reference handling in the budget planner to avoid invalid ledger inserts and SQLite foreign-key crashes.
- Enforced `content_text` archive byte limits and strict evidence-type sanitization.
- Added wallet evidence file/path/hash validation under a configured archive root.
- Added explicit ledger spend summary APIs for experiment totals and spend-by-category aggregation.
- Expanded policy taxonomy so bounded purchase/spend categories can be explicitly authorized without weakening blocked-category behavior.

## Fixed P2 issues

- Removed the stale Copilot/OpenCode split-work guidance from `docs/CODE_REVIEW1_TODO.md`.
- Added a regression test to keep the stale split-work phrases out of the review docs.
- Marked `docs/CODE_REVIEW2_TODO.md` complete.

## Changed files

- `src/openclaw_moneybot/shared/config.py`
- `src/openclaw_moneybot/shared/contracts.py`
- `src/openclaw_moneybot/plugins/wallet_governor_service/models.py`
- `src/openclaw_moneybot/plugins/wallet_governor_service/service.py`
- `src/openclaw_moneybot/skills/moneybot_policy_guard/rules.py`
- `src/openclaw_moneybot/skills/moneybot_policy_guard/taxonomy.py`
- `src/openclaw_moneybot/skills/budget_and_roi_planner/runner.py`
- `src/openclaw_moneybot/skills/receipt_and_evidence_archiver/storage.py`
- `src/openclaw_moneybot/skills/ledger_skill/models.py`
- `src/openclaw_moneybot/skills/ledger_skill/repository.py`
- `src/openclaw_moneybot/skills/ledger_skill/service.py`
- `src/openclaw_moneybot/orchestration/workflow.py`
- `docs/CODE_REVIEW1_TODO.md`
- `docs/CODE_REVIEW2_TODO.md`
- `tests/unit/test_budget_and_roi_planner.py`
- `tests/unit/test_receipt_and_evidence_archiver.py`
- `tests/unit/test_ledger_skill.py`
- `tests/unit/test_moneybot_policy_guard.py`
- `tests/unit/test_review_docs.py`
- `tests/unit/test_wallet_governor_http.py`
- `tests/unit/test_wallet_governor_service.py`
- `tests/integration/helpers.py`
- `tests/integration/test_wallet_http_integration.py`

## Test command

`uv run --python 3.11 ruff check . && uv run --python 3.11 mypy . && uv run --python 3.11 pytest`

## Test result summary

- `ruff check .` passed
- `mypy .` passed
- `pytest` passed with `296 passed`

## Deferred work

- No additional implementation items from `docs/CODE_REVIEW2_TODO.md` remain open.
- Real BTC connectivity is still intentionally deferred pending another review pass.

## Safety notes

- Wallet authorization now requires executable policy metadata, matching ledger context, valid budget/TOS references, and verified evidence artifacts before send.
- Quote and send paths reject malformed destinations and send-all semantics.
- Evidence validation fails closed on missing files, hash mismatches, or archive-path escapes.
- Send-after-success lock failures return success with a warning and record audit state, per the clarified repository decision.

## Default safety confirmation

- Real wallet spending remains disabled by default.
- Bitcoin Core backend remains disabled by default.
