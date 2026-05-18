# Copilot Instructions for OpenClaw MoneyBot

## Project intent

OpenClaw MoneyBot is a constrained local experiment runner, not a general-purpose autonomous finance agent.

Optimize for **bounded autonomy**:

- Allow OpenClaw to explore, rank, plan, and execute small approved money-making experiments.
- Prevent unbounded risk, unsafe automation, policy bypasses, and hidden side effects.
- Preserve complete auditability through the ledger and evidence archive.

Read these documents before making architecture-level changes:

- `docs/OPENCLAW_MONEYBOT_PROJECT_SPEC.md`
- `docs/OPENCLAW_MONEYBOT_ARCHITECTURE.md`

## Required engineering stack

- Use **Python 3.11**.
- Use **uv** for Python environment and dependency management.
- Use **ruff** and **mypy** as required quality gates.
- Use **pytest** for unit tests.
- Do **not** hide, suppress, or ignore lint errors or warnings as a shortcut. Fix them.

## Core architecture rules

The system is layered:

1. Local LLM
2. OpenClaw orchestration
3. Narrow skills
4. Deterministic validators and schemas
5. Governed plugins and services
6. Local ledger, archive, wallet, and email account

The LLM may reason and propose, but it must not directly control dangerous resources.

Keep these boundaries intact:

- Money only goes through `wallet_governor_service`.
- Ledger writes only go through `ledger_skill` or a dedicated ledger API.
- Evidence storage only goes through `receipt_and_evidence_archiver`.
- Email sending, if enabled later, must go through an email governor.
- Browser and shell automation are dangerous and must stay constrained by policy, allowlists, and workspace boundaries.

## v1 skill model

Keep the nine v1 skills narrow and separately testable:

1. `moneybot_policy_guard`
2. `opportunity_scout`
3. `tos_legal_checker`
4. `budget_and_roi_planner`
5. `ledger_skill`
6. `wallet_governor_client`
7. `email_drafter`
8. `receipt_and_evidence_archiver`
9. `experiment_reviewer`

Do not collapse these into one broad "do everything" agent.

Each skill should have:

- clear inputs and outputs
- schema validation
- explicit error behavior
- unit tests
- documented acceptance criteria

## Required workflow

Default workflow:

1. `opportunity_scout` finds candidates.
2. `moneybot_policy_guard` performs filtering.
3. `tos_legal_checker` reviews rules, legality, and terms.
4. `budget_and_roi_planner` creates a budgeted experiment.
5. `moneybot_policy_guard` checks the proposed execution plan.
6. `ledger_skill` records the approved plan.
7. Execution skills perform permitted actions.
8. `wallet_governor_client` requests payment only if needed and approved.
9. `receipt_and_evidence_archiver` archives proof.
10. `ledger_skill` records outputs and transaction metadata.
11. `experiment_reviewer` records the review.

Do not skip policy, budget, ledger, or evidence steps.

## Hard safety constraints

Treat these as non-negotiable:

- No autonomous crypto trading, gambling, DeFi, NFT, airdrop, or speculative token flows.
- No fake identities, spam, phishing, credential harvesting, malware, exploit behavior, or fake reviews.
- No handling money for other people.
- No access to personal accounts or personal email.
- No direct `bitcoin-cli` usage from OpenClaw-facing code.
- No direct access to Bitcoin Core datadir, wallet backups, passphrases, seed phrases, private keys, RPC cookies, or similar secrets.
- No unrestricted shell authority, root access, or sudo-based workflows.

Unknown or ambiguous high-risk actions should fail closed as `block` or `needs_review`, not silently proceed.

## Wallet and money handling

The wallet governor is the only component allowed to talk to the Bitcoin wallet.

Preserve these invariants:

- No spending without policy approval.
- No spending without a budget plan.
- No spending without a ledger entry created before send.
- No send-all behavior.
- Enforce hard limits for single payment, daily spend, and weekly spend.
- Require purpose, counterparty, and traceable metadata.
- Log before and after payment attempts.

OpenClaw should never receive wallet secrets.

## Ledger and evidence expectations

The SQLite ledger is the local system of record. Prefer SQLite for v1.

Every meaningful action should leave durable records for:

- opportunities
- policy decisions
- TOS and legal checks
- budget plans
- experiments
- spend requests
- wallet transactions
- email drafts and events
- evidence artifacts
- experiment reviews
- audit events

Archive proof aggressively:

- terms and rules pages
- receipts and invoices
- screenshots and HTML snapshots
- transaction metadata
- email drafts and responses
- deliverables and submissions

Link artifacts back to ledger records.

## LLM output handling

Assume the LLM is imperfect and untrusted.

- Validate all structured outputs with schemas.
- Fail closed on invalid or malformed output.
- Prefer explicit prompts and narrow responsibilities.
- Do not rely on instruction-following alone for safety.
- Do not put secrets into prompts.

## Implementation guidance

When generating code:

- Prefer deterministic logic for policy, validation, limits, and storage.
- Reuse shared models and validators instead of duplicating schemas.
- Use clear types and avoid broad `Any` where a structured model should exist.
- Keep modules small and composable.
- Keep services separately testable from orchestration logic.
- Prefer local filesystem storage for evidence archives.
- Do not add demo-only safety shortcuts.
- Do not leave critical safety rules as comments without implementation.

## Testing and quality expectations

- Add or update `pytest` tests for behavior changes.
- Cover happy paths, blocked paths, and malformed-input paths where applicable.
- Run `ruff`, `mypy`, and relevant tests after changes.
- Fix lint and type issues instead of suppressing them.

## Bias for decisions

When choosing between two implementations, prefer the one that is:

1. more auditable
2. more deterministic
3. safer by default
4. easier to test
5. less likely to bypass policy, ledger, or wallet controls

## Memory file
- You have access to a persistent memory file, memory_copilot.md, that stores context about the project, previous interactions, and user preferences.
- Use this memory to inform your decisions, remember user preferences, and maintain continuity across sessions. 
- Before sending back a response, update memory_copilot.md with any new relevant information learned during the interaction. Make sure to timestamp and format entries clearly.
- Include the GitHub Copilot model used for the entry in the heading line so memory history records both time and model (for example: `## 2024-06-01T12:00:00Z - GPT-5.4 - User prefers concise responses`).
- **NEVER fabricate or guess timestamps.** Always obtain the current time by running `date -u +"%Y-%m-%dT%H:%M:%SZ"` in the terminal immediately before writing the entry. If the entry describes a specific commit, use `git log -1 --format="%aI" <hash>` for that commit's actual timestamp.
- For each entry, add an ISO 8601 timestamp and a brief description of the information added. For example:
```markdown

## 2024-06-01T12:00:00Z - GPT-5.4 - User prefers concise responses
- User has expressed a preference for concise, to-the-point answers without unnecessary elaboration.
```

