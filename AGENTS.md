# AGENTS.md - OpenCode session context for OpenClaw MoneyBot

## Purpose

OpenClaw MoneyBot is a constrained autonomous experiment-runner for legal money-making opportunities. Local LLM only. No OpenAI/Anthropic APIs. Very small BTC budget. Deterministic safety, not prompt-trust.

Key principle: Reasoning is cheap and untrusted. Authority (money, email, policy) is enforced by deterministic service boundaries and schemas, not instructions.

## Architecture essentials

High-level structure:

- Local LLM → OpenClaw orchestration → Narrow skills → Deterministic validators → Governed plugins → SQLite ledger + evidence archive.

Nine core skills:
- moneybot_policy_guard
- opportunity_scout
- tos_legal_checker
- budget_and_roi_planner
- ledger_skill
- wallet_governor_client
- email_drafter
- receipt_and_evidence_archiver
- experiment_reviewer

Each skill:
- Has a single SKILL.md (its spec).
- Defines strict JSON input/output.
- Is independently testable.
- Must not bypass other skills.

Plugins:
- wallet_governor_service: the only gateway to BTC wallet.
- ledger_api: optional external interface for ledger.
- Each plugin is an executable service or library, not a prompt.

Design rule:
- Do not merge skills into a monolith.
- Do not let a single prompt control money or email without policy + ledger + wallet-governor checks.

## How to work on this repo

- Read docs/OPENCLAW_MONEYBOT_PROJECT_SPEC.md for acceptance criteria.
- Read docs/OPENCLAW_MONEYBOT_ARCHITECTURE.md for data flows, trust boundaries, and deployment model.
- Read each skill’s SKILL.md for exact JSON schemas and behavior.
- Never store wallet secrets, seed phrases, or personal credentials in repo files.
- Never embed API keys for external LLMs; this project uses local inference only.

When implementing:
- Respect the skill boundaries; do not merge behavior unless both specs allow it.
- Use schemas for all LLM-generated JSON. Validate before use; fail closed on invalid JSON.
- Keep wallet operations behind wallet_governor_service; never expose RPC keys to the LLM.
- Ensure policy checks run before spend/send/submit.
- Ensure ledger writes happen before irreversible actions.
- Write deterministic tests for edge cases and blocked scenarios.

## Non-obvious constraints

- The bot may not directly call bitcoin-cli, wallet RPC, or browser extensions.
- The bot may not impersonate a human or fake affiliation.
- The bot may not run crypto trading, gambling, prediction markets, DeFi yield farming, or NFT speculation.
- Email is draft-only by default; sending is optional and gated.
- SQLite is the canonical source of truth for ledger records and experiment metadata.
