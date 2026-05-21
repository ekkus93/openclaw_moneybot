# OpenClaw MoneyBot Project Specification

## 1. Project Name

**OpenClaw MoneyBot**

## 2. Purpose

OpenClaw MoneyBot is a constrained autonomous business-experiment agent designed to find, evaluate, and execute small legal money-making opportunities using a tightly limited budget.

The initial working budget is approximately **$100 worth of Bitcoin** held in a dedicated hot wallet on a dedicated machine. The bot uses a **local LLM** as its reasoning engine and does not rely on OpenAI, Anthropic, or other hosted LLM APIs.

The project is not intended to create an unbounded trading bot, spam bot, financial intermediary, or general-purpose internet automation agent. It is intended to create a controlled, auditable, legally constrained experiment runner that can:

1. Discover small legitimate opportunities.
2. Evaluate legal, terms-of-service, budget, and operational risks.
3. Create concrete experiment plans.
4. Draft communications and execution steps.
5. Spend very small amounts only through a hard-limited wallet governor.
6. Archive evidence and receipts.
7. Record a complete ledger.
8. Review experiment outcomes and improve future decisions.

## 3. Core Design Principle

The bot must never be trusted merely because the LLM was instructed to behave safely.

Safety must be enforced by:

- Narrow skills.
- Explicit workflows.
- Deterministic validators.
- Tool-level permission boundaries.
- Wallet-governor spending limits.
- Ledger requirements.
- Evidence archival requirements.
- Blocklists for prohibited activity.
- No direct access to private keys, wallet backups, personal accounts, or unrestricted shell authority.

The local LLM may propose actions, but executable plugins and services must enforce the rules.

## 4. Operating Assumptions

The implementation should assume the following deployment environment:

- A dedicated physical or virtual machine for the bot.
- A dedicated Linux user for OpenClaw, for example `openclawbot`.
- A separate Bitcoin Core service user, for example `bitcoin`.
- A dedicated bot email account.
- No access to the user's personal accounts.
- No access to personal email, banking, brokerage, exchange, social media, or wallet accounts.
- Local LLM inference only.
- No OpenAI API key.
- No Anthropic API key.
- No general hosted LLM dependency.
- A small Bitcoin hot wallet funded with only the experiment budget.
- Wallet access only through a wallet-governor service.
- All bot activity logged to a local SQLite ledger.
- Evidence and receipts stored in a local archive directory.

## 5. Success Criteria

The project is successful when OpenClaw MoneyBot can run a complete controlled experiment loop:

1. Find at least 20 candidate opportunities.
2. Reject prohibited or legally risky opportunities.
3. Rank remaining opportunities.
4. Select one low-risk opportunity.
5. Produce a budgeted experiment plan.
6. Record the plan in the ledger.
7. Draft any required email or communication.
8. Request a small wallet payment only if required and policy-approved.
9. Archive receipts, web evidence, and transaction metadata.
10. Record outcomes.
11. Generate an experiment review with a continue/stop/retry decision.

For v1, it is acceptable if some steps require manual approval or manual execution. The core requirement is that the bot follows the correct pipeline and produces auditable records.

## 6. Non-Goals

The following are explicit non-goals:

- Autonomous crypto trading.
- Autonomous securities, options, forex, futures, or derivative trading.
- Prediction-market participation.
- Gambling.
- DeFi yield farming.
- NFT minting or trading.
- Token speculation.
- Airdrop farming.
- Fake-account creation.
- KYC evasion.
- Account farming.
- Spam outreach.
- Fake reviews.
- Paid manipulation.
- Scraping against terms of service.
- Credential harvesting.
- Phishing.
- Malware.
- Exploit deployment.
- Botnet behavior.
- Running as a money transmitter, broker, escrow, exchange, mixer, or payment processor.
- Handling money for other people.
- Accessing personal user accounts.
- Replacing legal, tax, or accounting advice.

If a proposed opportunity depends on any of these, the system must reject it.

## 7. Primary User Story

As the owner/operator, I want to run OpenClaw MoneyBot on a dedicated computer with a local LLM and a $100 Bitcoin hot wallet, so that it can legally explore small money-making opportunities without endangering my personal accounts, creating unbounded financial risk, or performing prohibited activity.

## 8. Secondary User Stories

### 8.1 Opportunity Discovery

As the bot, I need to search for small, legitimate opportunities that a technically capable solo operator can pursue with under $100.

Examples:

- Paid open-source bounties.
- Documentation bounties.
- Small coding tasks.
- Legal contests or hackathons.
- Micro-product ideas.
- Low-cost infrastructure experiments.
- Small legitimate service offerings.
- Manual-review lead generation.
- Small product validation tests.

### 8.2 Legal and Terms Filtering

As the bot, I need to reject opportunities that are illegal, deceptive, exploitative, regulated beyond the project scope, or in violation of platform terms.

### 8.3 Budgeting

As the bot, I need to calculate required spend, worst-case loss, expected return, break-even point, stop conditions, and success metrics before spending money.

### 8.4 Wallet Use

As the bot, I need to check wallet balance and request small payments through a wallet-governor API. I must not directly call `bitcoin-cli`, access wallet files, reveal wallet passphrases, or bypass spend limits.

### 8.5 Communication

As the bot, I need to draft honest business emails and submissions. Sending should be limited, rate-controlled, and never deceptive.

### 8.6 Evidence Capture

As the bot, I need to preserve proof of opportunity pages, terms, receipts, invoices, transaction IDs, submissions, email threads, and outcomes.

### 8.7 Review

As the bot, I need to review each experiment and decide whether to continue, stop, retry with changes, or block a class of opportunities.

## 9. Skill Set

The v1 system consists of nine core skills:

1. `moneybot_policy_guard`
2. `opportunity_scout`
3. `tos_legal_checker`
4. `budget_and_roi_planner`
5. `ledger_skill`
6. `wallet_governor_client`
7. `email_drafter`
8. `receipt_and_evidence_archiver`
9. `experiment_reviewer`

Each skill should remain narrow. Do not merge them into a single general-purpose agent skill.

## 10. Skill Responsibilities

### 10.1 `moneybot_policy_guard`

The central policy gatekeeper.

Responsibilities:

- Classify proposed actions as `allow`, `block`, or `needs_review`.
- Enforce prohibited activity rules.
- Detect regulated or high-risk financial activity.
- Detect deception, spam, fake identity, or terms-of-service risk.
- Require mitigations before risky actions continue.
- Return structured policy results.

This skill must be called before:

- Spending money.
- Sending email.
- Submitting forms.
- Creating accounts.
- Publishing content.
- Running browser automation.
- Executing opportunity plans.

### 10.2 `opportunity_scout`

The discovery and ranking skill.

Responsibilities:

- Find candidate opportunities.
- Extract key facts.
- Estimate required spend and possible reward.
- Identify obvious red flags.
- Rank candidates.
- Pass candidates to policy and legal/TOS checks.

This skill must not spend money, send email, create accounts, or submit forms.

### 10.3 `tos_legal_checker`

The terms and legal-risk review skill.

Responsibilities:

- Read opportunity rules and platform terms.
- Identify terms-of-service constraints.
- Identify payment rules.
- Identify eligibility requirements.
- Identify regulated activity risks.
- Reject unclear, deceptive, or prohibited opportunities.
- Produce a structured recommendation.

This skill is not a substitute for a lawyer. It is a conservative filter.

### 10.4 `budget_and_roi_planner`

The experiment economics skill.

Responsibilities:

- Convert an opportunity into a budgeted experiment.
- Estimate expected return and maximum loss.
- Define success metrics.
- Define stop conditions.
- Define break-even conditions.
- Reject opportunities with unclear economics.
- Produce a spend request only if justified.

### 10.5 `ledger_skill`

The system of record.

Responsibilities:

- Record opportunities.
- Record policy decisions.
- Record TOS/legal checks.
- Record budget plans.
- Record spend requests.
- Record wallet transactions.
- Record emails.
- Record receipts and evidence.
- Record experiment outcomes.
- Preserve auditability.

No spend or external action should happen without a ledger entry.

### 10.6 `wallet_governor_client`

The OpenClaw-facing wallet client.

Responsibilities:

- Call the wallet-governor service.
- Check wallet balance.
- Quote small payments.
- Submit small payment requests.
- Validate returned transaction metadata.
- Record wallet activity in the ledger.
- Never expose private keys, passphrases, wallet backups, or raw Bitcoin RPC to the LLM.

The client is not the policy enforcement layer by itself. The wallet-governor service must enforce limits even if the LLM misbehaves.

### 10.7 `email_drafter`

The communication drafting skill.

Responsibilities:

- Draft honest emails.
- Draft bounty submissions.
- Draft customer-support messages.
- Draft opportunity applications.
- Avoid spam, deception, fake identity, and misleading claims.
- Optionally pass approved drafts to an email-governor service.

For v1, draft-only mode is preferred.

### 10.8 `receipt_and_evidence_archiver`

The archive and proof skill.

Responsibilities:

- Save copies of opportunity pages.
- Save terms/rules pages.
- Save receipts and invoices.
- Save transaction IDs.
- Save email artifacts.
- Save submitted deliverables.
- Hash archived artifacts when practical.
- Link artifacts to ledger records.

### 10.9 `experiment_reviewer`

The feedback and evaluation skill.

Responsibilities:

- Review completed or abandoned experiments.
- Compare expected versus actual results.
- Calculate spend, revenue, and net result.
- Identify failures.
- Recommend continue/stop/retry/block.
- Feed lessons back into future opportunity scoring.

## 11. Required Workflow

The default workflow must be:

1. `opportunity_scout` finds candidates.
2. `moneybot_policy_guard` performs initial filtering.
3. `tos_legal_checker` reviews terms, rules, and legal/TOS risk.
4. `budget_and_roi_planner` creates a budgeted experiment.
5. `moneybot_policy_guard` checks the proposed execution plan.
6. `ledger_skill` records the approved plan.
7. Execution skills perform permitted actions.
8. `wallet_governor_client` requests payment only if needed and approved.
9. `receipt_and_evidence_archiver` archives proof.
10. `ledger_skill` records all outputs and transaction metadata.
11. `experiment_reviewer` reviews the result.

No skill should skip the policy, budget, ledger, or evidence steps.

## 12. Prohibited Workflow Shortcuts

The implementation must prevent these shortcuts:

- Opportunity discovery directly spending funds.
- Browser automation directly buying something.
- Email drafting directly sending bulk outreach.
- Wallet client spending without a policy result.
- Wallet client spending without a budget plan.
- Wallet client spending without a ledger entry.
- Ledger being updated after the fact only.
- Evidence archive omitted because action succeeded.
- Experiment review omitted because the bot moved on.
- LLM receiving the wallet passphrase.
- LLM receiving raw Bitcoin RPC credentials.
- LLM receiving wallet backup paths.
- LLM receiving personal account credentials.

## 13. Data Model Requirements

At minimum, the project must support the following record types:

- Opportunity.
- Policy decision.
- TOS/legal check.
- Budget plan.
- Spend request.
- Wallet transaction.
- Email draft.
- Email send event, if sending is enabled.
- Receipt.
- Evidence artifact.
- Experiment.
- Experiment review.

SQLite is preferred for v1 because it is local, inspectable, easy to back up, and adequate for the scale of this experiment.

## 14. Wallet Requirements

The v1 wallet is a Bitcoin hot wallet.

Required wallet constraints:

- Dedicated wallet for OpenClaw only.
- Funded with only the experiment budget.
- No personal wallet funds.
- No exchange withdrawal access.
- No browser wallet extension for v1.
- No direct OpenClaw access to `bitcoin-cli`.
- No direct OpenClaw access to Bitcoin Core datadir.
- No OpenClaw access to wallet passphrase.
- No OpenClaw access to wallet backup.
- Wallet activity only through wallet-governor service.
- Hard-coded maximum single payment.
- Hard-coded maximum daily payment.
- Hard-coded maximum weekly payment.
- `send-all` behavior must be impossible through the exposed API.
- Wallet service must log before and after payment attempts.

Suggested initial limits:

```yaml
max_wallet_balance_usd: 125
max_single_payment_usd: 10
max_daily_payment_usd: 20
max_weekly_payment_usd: 40
require_policy_approval: true
require_budget_plan: true
require_ledger_entry_before_send: true
block_send_all: true
```

## 15. Email Requirements

The v1 email account must be a dedicated bot-only account.

Required constraints:

- No access to the user's personal email.
- No contact import from personal accounts.
- No deceptive identity.
- No fake affiliation.
- No fake urgency.
- No bulk mailing.
- No scraped mailing lists.
- No repeated harassment follow-ups.
- No sending in v1 unless explicitly enabled.
- All email drafts must be archived and linked to an opportunity or experiment.

Suggested v1 mode:

```yaml
email_mode: draft_only
max_outbound_per_day: 0
```

Suggested later mode:

```yaml
email_mode: capped_send
max_outbound_per_day: 5
max_outbound_per_domain_per_day: 2
max_followups_per_thread: 1
```

## 16. Browser and Shell Requirements

Browser and shell capabilities must be treated as dangerous.

Browser constraints:

- Bot-owned accounts only.
- No personal accounts.
- No KYC flows without human review.
- No CAPTCHA bypass.
- No bot-evasion behavior.
- No mass signup.
- No unauthorized scraping.
- No purchases unless routed through the approved wallet-governor flow.

Shell constraints:

- No root.
- No sudo.
- Workdir-only file writes.
- No wallet datadir access.
- No secret file access.
- No LAN scanning.
- No background persistence installation.
- No hidden network services.
- No modifying system services except through human-approved deployment scripts.

## 17. Local LLM Requirements

The project should assume the LLM is imperfect, local, and possibly weaker than frontier hosted models.

Implementation implications:

- Use schemas everywhere.
- Validate every LLM output.
- Fail closed on invalid JSON.
- Avoid relying on subtle natural-language instruction following.
- Keep prompts explicit.
- Keep skill responsibilities narrow.
- Use deterministic gates for money and email.
- Use conservative defaults.
- Log raw model outputs for debugging when safe.
- Never put secrets in prompts.

## 18. Repository Layout Recommendation

Recommended repository layout:

```text
openclaw-moneybot/
  README.md
  docs/
    OPENCLAW_MONEYBOT_PROJECT_SPEC.md
    OPENCLAW_MONEYBOT_ARCHITECTURE.md
    OPENCLAW_MONEYBOT_FULL_IMPLEMENTATION_TODO.md
  skills/
    moneybot_policy_guard/
      SKILL.md
      TODO.md
    opportunity_scout/
      SKILL.md
      TODO.md
    tos_legal_checker/
      SKILL.md
      TODO.md
    budget_and_roi_planner/
      SKILL.md
      TODO.md
    ledger_skill/
      SKILL.md
      TODO.md
    wallet_governor_client/
      SKILL.md
      TODO.md
    email_drafter/
      SKILL.md
      TODO.md
    receipt_and_evidence_archiver/
      SKILL.md
      TODO.md
    experiment_reviewer/
      SKILL.md
      TODO.md
  plugins/
    wallet_governor_service/
    ledger_api/
    email_governor/
    browser_governor/
    operator_profile_store/
    rules_snapshot_gateway/
    wallet_observer_plugin/
    inbox_observer_plugin/
    opportunity_index_plugin/
    artifact_renderer_plugin/
    deadline_scheduler_plugin/
    download_quarantine_plugin/
    counterparty_snapshot_plugin/
    metrics_export_plugin/
  src/
    openclaw_moneybot/
      policy/
      ledger/
      wallet/
      email/
      archive/
      experiments/
      schemas/
      config/
  tests/
    unit/
    integration/
    fixtures/
```

## 19. Configuration Requirements

The project should use explicit configuration files. Suggested config names:

```text
config/moneybot.policy.yaml
config/wallet_governor.yaml
config/email_governor.yaml
config/ledger.yaml
config/archive.yaml
```

Configuration must not contain wallet passphrases or private keys if the LLM can read it.

Secrets must be stored outside OpenClaw-readable directories.

## 20. Acceptance Criteria for v1

v1 is complete when:

- All nine skill specs exist.
- All nine skill TODOs are implemented or explicitly deferred.
- The policy guard can classify allowed, blocked, and needs-review actions.
- The opportunity scout can produce structured candidate reports.
- The TOS/legal checker can produce structured risk checks.
- The budget planner can produce structured experiment plans.
- The ledger can store all required records.
- The evidence archiver can store and link artifacts.
- The wallet-governor client can call a mocked or real governor service.
- The wallet-governor service enforces spend limits.
- The email drafter operates in draft-only mode.
- The experiment reviewer produces final reviews.
- Invalid LLM output fails closed.
- Money spending cannot occur without policy approval, budget plan, and ledger entry.
- Tests cover happy path, blocked path, and malformed-input path.
- The system can run one end-to-end dry-run experiment without real spending.
- The system can run one tiny real-wallet payment test under strict limits.

## 21. Implementation Priorities

Build in this order:

1. Schemas and shared types.
2. Ledger.
3. Policy guard.
4. Evidence archive.
5. Opportunity scout.
6. TOS/legal checker.
7. Budget planner.
8. Experiment reviewer.
9. Wallet-governor service with mock mode.
10. Wallet-governor client.
11. Email drafter.
12. Optional email-governor send mode.
13. End-to-end orchestration.

Do not implement wallet spending before ledger and policy checks exist.

## 22. Copilot Implementation Guidance

When implementing this project:

- Do not create demo-only code paths.
- Do not leave safety checks as comments.
- Do not bypass schemas.
- Do not use broad `Any` types where structured models are required.
- Do not store secrets in repo files.
- Do not make network calls in unit tests.
- Do not require external paid APIs.
- Prefer deterministic unit tests.
- Prefer SQLite for the ledger.
- Prefer local filesystem storage for evidence archives.
- Fail closed on unknown action categories.
- Use clear error types.
- Keep skills individually testable.
- Keep plugin services separately testable.
- Ensure wallet spending is impossible unless all required gates pass.

## 23. Final Summary

OpenClaw MoneyBot is not a general-purpose autonomous financial agent. It is a tightly constrained local experiment runner with a small Bitcoin budget, a dedicated machine, a local LLM, a policy-first workflow, a complete ledger, and a hard-limited wallet interface.

The project should be implemented as a set of narrow skills plus deterministic service plugins, not as one large autonomous agent with unrestricted tools.
