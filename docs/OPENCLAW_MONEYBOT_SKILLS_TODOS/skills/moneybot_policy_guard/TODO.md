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

# TODO — `moneybot_policy_guard`

## Goal

Implement the deterministic safety and legality gatekeeper for all MoneyBot actions. This skill must classify proposed actions as `allow`, `block`, or `needs_review` before any spend, email, browser submission, or account action occurs.

## Implementation tasks

### 1. Skill scaffolding

- [ ] Create the implementation module for `moneybot_policy_guard`.
  - [ ] Add `__init__.py` if using Python packages.
  - [ ] Add `models.py` for Pydantic v2 input/output contracts.
  - [ ] Add `rules.py` for deterministic rule evaluation.
  - [ ] Add `taxonomy.py` for categories, blocked patterns, and risk labels.
  - [ ] Add `service.py` or `runner.py` exposing the OpenClaw skill entrypoint.
- [ ] Keep `SKILL.md` as the human-readable spec.
- [ ] Add `tests/skills/test_moneybot_policy_guard.py`.

### 2. Define input contract

- [ ] Create `PolicyCheckRequest` model.
  - [ ] `action_id`
  - [ ] `action_type`
  - [ ] `description`
  - [ ] `category`
  - [ ] `counterparty`
  - [ ] `amount_usd`
  - [ ] `asset`
  - [ ] `source_urls`
  - [ ] `planned_tools`
  - [ ] `user_approval_present`
  - [ ] `metadata`
- [ ] Validate required fields.
  - [ ] Reject empty descriptions.
  - [ ] Reject missing category for external actions.
  - [ ] Reject missing amount for spend actions.
  - [ ] Reject missing counterparty for payment/email actions.
- [ ] Normalize action category strings to canonical enum values.
- [ ] Preserve the original raw request in a safe audit field.

### 3. Define output contract

- [ ] Create `PolicyDecision` model.
  - [ ] `decision`: `allow | block | needs_review`
  - [ ] `risk_level`: `low | medium | high | critical`
  - [ ] `blocked_reasons`
  - [ ] `required_mitigations`
  - [ ] `matched_rules`
  - [ ] `human_review_reason`
  - [ ] `safe_next_steps`
  - [ ] `expires_at`
- [ ] Include a stable `policy_decision_id`.
- [ ] Include a `policy_version` string.
- [ ] Include a deterministic hash of the normalized request.

### 4. Build prohibited-category taxonomy

- [ ] Encode hard-block categories.
  - [ ] Gambling.
  - [ ] Prediction markets.
  - [ ] Securities/options/forex/leverage trading.
  - [ ] Autonomous crypto trading/speculation.
  - [ ] Handling money for other people.
  - [ ] Money transmission, escrow, exchange, brokering, mixing/tumbling.
  - [ ] KYC evasion, fake identity, account farming.
  - [ ] Spam, mass outreach, deceptive marketing, fake reviews.
  - [ ] Phishing, malware, credential harvesting, exploit deployment.
  - [ ] Scraping or automation that violates platform rules.
  - [ ] Adult, illegal goods, regulated weapons, drugs, or other high-risk commerce.
- [ ] Encode `needs_review` categories.
  - [ ] Anything involving legal uncertainty.
  - [ ] Anything involving recurring subscription charges.
  - [ ] Anything involving identity verification.
  - [ ] Anything involving user data collection.
  - [ ] Anything involving affiliate marketing.
  - [ ] Anything involving platform API terms that have not been checked.
- [ ] Encode explicitly allowed low-risk categories.
  - [ ] Research-only opportunity analysis.
  - [ ] Draft-only email preparation.
  - [ ] Static landing page generation.
  - [ ] Internal budget planning.
  - [ ] Ledger/evidence archival.

### 5. Implement rule engine

- [ ] Make evaluation deterministic and ordered.
  - [ ] Hard-block rules run first.
  - [ ] Missing-info rules run second.
  - [ ] Review-required rules run third.
  - [ ] Allow rules run last.
- [ ] Never let an LLM override hard-block rules.
- [ ] Add keyword and category matching, but do not rely on keywords alone.
- [ ] Add tool-risk checks.
  - [ ] Wallet tool requested without budget plan -> block.
  - [ ] Email send requested without draft approval -> needs_review or block.
  - [ ] Browser form submission requested without TOS check -> needs_review.
  - [ ] Shell execution touching wallet files -> block.
- [ ] Add amount-risk checks.
  - [ ] Missing amount on payment -> block.
  - [ ] Above configured max single spend -> block.
  - [ ] Above configured daily spend -> block.
- [ ] Add counterparty checks.
  - [ ] Missing recipient/counterparty for spend -> block.
  - [ ] Counterparty is unknown and payment is requested -> needs_review.

### 6. Ledger integration

- [ ] Require the skill to produce a policy decision record suitable for `ledger_skill`.
- [ ] Add a function to serialize decisions into ledger-ready JSON.
- [ ] Ensure policy decisions can be linked by ID to later spend/email/browser actions.
- [ ] Add idempotency key support so repeated checks do not create conflicting records.

### 7. Configuration

- [ ] Add config loading.
  - [ ] Blocked categories.
  - [ ] Review-required categories.
  - [ ] Max single spend.
  - [ ] Max daily spend.
  - [ ] Allowed action types.
  - [ ] Policy version.
- [ ] Validate config at startup.
- [ ] Fail closed if config is missing or invalid.

### 8. Tests

- [ ] Test each hard-block category.
- [ ] Test each `needs_review` category.
- [ ] Test allow decisions for safe research-only actions.
- [ ] Test wallet action without budget plan -> block.
- [ ] Test wallet action above spend limit -> block.
- [ ] Test email send without approval -> block or needs_review according to config.
- [ ] Test unknown category -> needs_review.
- [ ] Test missing amount on spend -> block.
- [ ] Test missing counterparty on spend -> block.
- [ ] Test deterministic output for identical inputs.
- [ ] Test policy version is included.
- [ ] Test that dangerous instructions in `description` cannot override policy.

### 9. Acceptance criteria

- [ ] The policy guard never returns `allow` for prohibited categories.
- [ ] Unknown or ambiguous external actions become `needs_review`, not `allow`.
- [ ] Every decision has structured reasons and matched rules.
- [ ] Every spend/email/browser-submit workflow can require a policy decision ID.
- [ ] The skill works offline with fixture data.
