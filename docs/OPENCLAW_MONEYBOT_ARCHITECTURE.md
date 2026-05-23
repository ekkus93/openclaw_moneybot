# OpenClaw MoneyBot Architecture

## 1. Architecture Overview

OpenClaw MoneyBot is a layered system:

```text
Local LLM
  ↓
OpenClaw orchestration
  ↓
Narrow skills
  ↓
Deterministic validators and schemas
  ↓
Governed plugins/services
  ↓
Local ledger, archive, wallet, email account
```

The LLM is allowed to reason and propose. It is not allowed to directly control dangerous resources.

Dangerous operations must go through deterministic service boundaries:

- Money goes through `wallet_governor_service`.
- Ledger writes go through `ledger_skill` or `ledger_api`.
- Evidence storage goes through `receipt_and_evidence_archiver`.
- Email sending, if ever enabled, goes through an email governor.
- Browser and shell automation must be constrained by allowlists and workspace boundaries.

## 2. Major Components

### 2.1 Local LLM Runtime

The local LLM provides reasoning and text generation.

Examples:

- llama-server.
- Ollama.
- Other local OpenAI-compatible or OpenClaw-supported local inference servers.

Architecture assumptions:

- Bound to localhost or an isolated network interface.
- No hosted LLM API keys.
- No secrets included in prompts.
- LLM output must be schema-validated before use.
- Invalid output fails closed.

### 2.2 OpenClaw Orchestrator

OpenClaw coordinates the skills.

Responsibilities:

- Select relevant skill.
- Provide task context.
- Enforce workflow order.
- Pass structured outputs between skills.
- Call tool/plugin interfaces.
- Keep run logs.
- Avoid granting unnecessary tool access.

OpenClaw should not directly receive wallet secrets, Bitcoin Core RPC credentials, email credentials, or personal-account credentials.

### 2.3 Skills

Skills are high-level behavior specifications and implementation modules.

The nine v1 skills are:

```text
moneybot_policy_guard
opportunity_scout
tos_legal_checker
budget_and_roi_planner
ledger_skill
wallet_governor_client
email_drafter
receipt_and_evidence_archiver
experiment_reviewer
```

Each skill should have:

- `SKILL.md`
- `TODO.md`
- Input schema.
- Output schema.
- Unit tests.
- Error behavior.
- Acceptance criteria.

### 2.4 Plugins and Services

Plugins/services perform concrete actions.

Required or recommended services:

```text
wallet_governor_service
ledger_api
email_governor
archive_store
browser_governor
```

Not every service is required in v1, but the architecture should leave clean boundaries for them.

Implemented helper plugins for the first-party plugin wave:

```text
operator_profile_store
rules_snapshot_gateway
wallet_observer_plugin
inbox_observer_plugin
opportunity_index_plugin
artifact_renderer_plugin
deadline_scheduler_plugin
download_quarantine_plugin
counterparty_snapshot_plugin
metrics_export_plugin
brave_search_plugin
wikipedia_research_plugin
arxiv_research_plugin
openalex_research_plugin
biomedical_research_plugin
mastodon_discovery_plugin
bluesky_discovery_plugin
stock_market_data_plugin
crypto_market_data_plugin
inner_voice_plugin
```

Plugin rollout rules:

- These helper plugins are optional for the default workflow and are gated by explicit config sections with `enabled` flags.
- Service-style separation remains reserved for components that need process isolation (`wallet_governor_service`, `ledger_api`, `email_governor`, `browser_governor`); the PLUGINS1 helpers stay as local Python modules.
- Read-only-by-default helpers include `wallet_observer_plugin` and `opportunity_index_plugin`; stateful helpers may write only to approved local paths plus the ledger/evidence archive.
- Plugin failures are fail-closed: invalid input, stale snapshots, quarantine rejection, or missing required helper data must block the dependent skill path instead of silently falling back.
- Plugins do not implement internal retry loops; callers provide any timeout policy, and persisted plugin operations must remain idempotent through deterministic file roots and ledger-linked records.

The `inner_voice_plugin` is a special read-only challenger plugin:

- it produces structured critique, bounded debate turns, and required Arbiter escalation records
- it uses direct provider-specific adapters for OpenAI, Ollama, and llama-server
- the llama-server adapter only performs minimal OpenAI-compatible text-part joining before strict
  JSON validation; it does not do semantic rewriting or fallback parsing
- it does **not** use LiteLLM or another generic LLM routing proxy
- it archives prompt, response, debate transcript, and Arbiter artifacts through the evidence archive
- it records debate lifecycle audit events for session start, completion, Arbiter escalation, and Arbiter invocation failure
- it honors debate transcript archival settings so operators can keep full transcript capture enabled or
  fall back to placeholder transcript artifacts plus bounded summary metadata
- it remains advisory: deterministic policy, TOS/legal, budget, ledger, and wallet controls still
  outrank all inner-voice and Arbiter output

In the current implementation, the default dry-run workflow uses configured inner-voice review
passes at selected stages. Multi-round OpenClaw-versus-inner-voice debate is exposed through an
explicit orchestration seam rather than being implicitly fabricated inside the dry-run path.

### 2.5 SQLite Ledger

The ledger is the authoritative local database.

Responsibilities:

- Store all opportunity, policy, budget, spend, transaction, email, receipt, evidence, and experiment review records.
- Provide durable audit trails.
- Support export to JSONL/CSV.
- Support reconciliation with wallet transactions and archived evidence.

### 2.6 Evidence Archive

The evidence archive stores proof files.

Examples:

- HTML snapshots.
- Screenshots.
- Receipts.
- Invoices.
- Email drafts.
- Email responses.
- Submitted deliverables.
- Transaction metadata.
- Terms/rules pages.
- JSON outputs from skills.

Files should be linked from the ledger.

### 2.7 Wallet Governor Service

The wallet-governor service is the only component allowed to talk to the Bitcoin wallet.

Responsibilities:

- Read wallet balance.
- Quote spend.
- Validate spend request.
- Enforce spending caps.
- Reject prohibited spend categories.
- Prevent send-all behavior.
- Unlock wallet only briefly if using an encrypted Bitcoin Core wallet.
- Send small payment only after all gates pass.
- Lock wallet after payment.
- Return txid and metadata.
- Log request and response.
- Never expose passphrase or RPC credentials to OpenClaw.

### 2.8 Email Governor

The email-governor service is optional for v1.

v1 should default to draft-only mode.

When sending is enabled, the email governor must:

- Enforce rate limits.
- Block deceptive content.
- Block bulk sending.
- Block repeated follow-ups.
- Ensure emails are linked to approved opportunities/experiments.
- Archive outgoing messages.
- Log all sends.

## 3. Trust Boundaries

### 3.1 Untrusted or Semi-Trusted Components

Treat these as untrusted or semi-trusted:

- LLM-generated plans.
- LLM-generated JSON.
- Browser page content.
- Emails received by the bot.
- Opportunity descriptions.
- Third-party websites.
- Downloaded files.
- Marketplace listings.
- Bounty descriptions.
- Any text that could contain prompt injection.

### 3.2 Trusted Components

These should be deterministic and trusted after testing:

- Schema validators.
- Policy guard deterministic checks.
- Wallet-governor hard limits.
- Ledger write logic.
- Evidence archive path sanitizer.
- Config loader.
- Secret loading code.
- Unit tests.

### 3.3 Secret Boundary

The LLM and skills must not see:

- Bitcoin wallet passphrase.
- Bitcoin Core RPC cookie.
- Wallet backup path.
- Wallet private keys.
- Seed phrase.
- Personal account credentials.
- Personal email tokens.
- Exchange credentials.
- Root credentials.
- SSH private keys.

Secrets should only be available to the specific service process that needs them.

## 4. Process and User Isolation

Recommended Linux users:

```text
openclawbot  -> runs OpenClaw and local skill code
bitcoin      -> runs Bitcoin Core
walletgov    -> runs wallet-governor service, if separate from bitcoin user
```

Recommended permissions:

- `openclawbot` cannot read Bitcoin datadir.
- `openclawbot` cannot read wallet-governor env file.
- `openclawbot` cannot read wallet backup files.
- `openclawbot` cannot use sudo.
- `bitcoin` owns Bitcoin Core datadir.
- `walletgov` can call wallet RPC or execute restricted wallet operations.
- Ledger and archive directories are writable only by intended service users.

## 5. Network Boundaries

Recommended network exposure:

```text
Local LLM server:        127.0.0.1 only
Bitcoin Core RPC:        127.0.0.1 only
Wallet governor API:     127.0.0.1 only
Ledger API:              127.0.0.1 only
Email governor API:      127.0.0.1 only
OpenClaw dashboard:      localhost or authenticated only
```

Firewall:

- Deny incoming by default.
- Allow outgoing by default for v1, unless stricter egress controls are added.
- Do not expose Bitcoin RPC to LAN or internet.
- Do not expose wallet governor to LAN or internet.

## 6. Data Flow: Opportunity Discovery

```text
User mission
  ↓
OpenClaw
  ↓
opportunity_scout
  ↓
CandidateOpportunity[]
  ↓
moneybot_policy_guard
  ↓
PolicyDecision[]
  ↓
ledger_skill
```

Output object:

```json
{
  "opportunity_id": "opp_...",
  "name": "Example opportunity",
  "category": "bounty",
  "source_url": "https://example.com",
  "required_spend_usd": 0,
  "estimated_revenue_usd": 50,
  "max_loss_usd": 0,
  "obvious_red_flags": [],
  "recommended_next_step": "Run TOS/legal check"
}
```

Rules:

- Discovery does not spend.
- Discovery does not submit forms.
- Discovery does not create accounts.
- Discovery does not send email.
- Discovery must pass candidates to policy and TOS/legal checking.

## 7. Data Flow: Policy Check

```text
Proposed action
  ↓
moneybot_policy_guard
  ↓
PolicyDecision
  ↓
ledger_skill
```

Output object:

```json
{
  "decision": "allow",
  "risk_level": "low",
  "blocked_reasons": [],
  "required_mitigations": [],
  "notes": "No prohibited category detected."
}
```

Rules:

- Unknown categories default to `needs_review` or `block`.
- Spending requires explicit `allow`.
- Email sending requires explicit `allow`.
- Browser form submission requires explicit `allow`.
- High-risk financial activity is blocked.
- Handling other people's funds is blocked.

## 8. Data Flow: TOS and Legal Review

```text
CandidateOpportunity
  ↓
tos_legal_checker
  ↓
TermsLegalCheck
  ↓
ledger_skill
```

Output object:

```json
{
  "allowed": true,
  "confidence": "medium",
  "platform_terms_summary": "Summary of relevant rules.",
  "red_flags": [],
  "required_records": ["terms_snapshot", "submission_receipt"],
  "final_recommendation": "proceed"
}
```

Rules:

- Missing or unreadable terms should not be treated as approval.
- Ambiguous requirements should result in `human_review`.
- Opportunities requiring deception, fake accounts, spam, or regulated activity must be rejected.

## 9. Data Flow: Budget Planning

```text
Approved opportunity
  ↓
budget_and_roi_planner
  ↓
BudgetPlan
  ↓
moneybot_policy_guard
  ↓
ledger_skill
```

Output object:

```json
{
  "experiment_name": "Example experiment",
  "spend_required_usd": 8,
  "max_loss_usd": 8,
  "expected_revenue_usd": 25,
  "break_even_condition": "One sale at $10 after fees.",
  "success_metric": "At least one qualified lead within 7 days.",
  "stop_condition": "Stop if no leads after 7 days.",
  "recommended_budget_usd": 8,
  "decision": "execute"
}
```

Rules:

- No spend without max loss.
- No spend without stop condition.
- No spend without expected outcome.
- Recurring charges require explicit handling.
- If the economics are speculative, decision should be `simulate` or `reject`.

## 10. Data Flow: Wallet Spending

```text
BudgetPlan
  ↓
moneybot_policy_guard
  ↓
ledger_skill creates SpendRequest
  ↓
wallet_governor_client
  ↓
wallet_governor_service
  ↓
Bitcoin Core wallet
  ↓
WalletTransaction
  ↓
ledger_skill
  ↓
receipt_and_evidence_archiver
```

Preconditions:

- Policy decision is `allow`.
- TOS/legal result is `proceed`.
- Budget decision is `execute`.
- Spend request exists in ledger.
- Amount is below hard limits.
- Category is not blocked.
- Purpose and counterparty are present.
- Wallet-governor service confirms daily/weekly limits.

Request object:

```json
{
  "spend_request_id": "spend_...",
  "amount_usd_estimate": 7.5,
  "btc_address": "bc1...",
  "purpose": "Purchase domain for approved experiment.",
  "counterparty": "Example registrar",
  "category": "infrastructure",
  "policy_decision_id": "policy_...",
  "budget_plan_id": "budget_...",
  "ledger_prewrite_id": "ledger_..."
}
```

Response object:

```json
{
  "status": "sent",
  "txid": "transaction id",
  "amount_btc": "0.00010000",
  "fee_btc": "0.00000300",
  "amount_usd_estimate": 7.5,
  "created_at": "2026-05-17T00:00:00Z"
}
```

Hard wallet service rules:

- Reject send-all.
- Reject amount above max single payment.
- Reject daily limit exceeded.
- Reject weekly limit exceeded.
- Reject blocked categories.
- Reject missing purpose.
- Reject missing counterparty.
- Reject missing policy approval.
- Reject missing budget plan.
- Reject missing ledger prewrite.
- Never return wallet passphrase.
- Never expose private keys.
- Never expose wallet backup paths.

## 11. Data Flow: Email Drafting

```text
Approved opportunity or experiment
  ↓
email_drafter
  ↓
DraftEmail
  ↓
moneybot_policy_guard
  ↓
ledger_skill
  ↓
optional email_governor
  ↓
archive
```

Draft object:

```json
{
  "email_id": "email_...",
  "mode": "draft_only",
  "to": "recipient@example.com",
  "subject": "Short truthful subject",
  "body": "Plain text body",
  "purpose": "Apply for approved bounty.",
  "related_opportunity_id": "opp_...",
  "related_experiment_id": "exp_...",
  "risk_flags": []
}
```

Rules:

- Draft-only by default.
- No fake identity.
- No misleading subject.
- No fake affiliation.
- No bulk sending.
- No scraped mass lists.
- No repeated follow-ups.
- No sending without policy approval.
- No sending without ledger record.

## 12. Data Flow: Evidence Archive

```text
Action result
  ↓
receipt_and_evidence_archiver
  ↓
Artifact files
  ↓
Artifact metadata
  ↓
ledger_skill
```

Artifact metadata:

```json
{
  "artifact_id": "artifact_...",
  "artifact_type": "receipt",
  "path": "archive/2026/05/17/artifact_...",
  "sha256": "hash",
  "source_url": "https://example.com",
  "related_record_type": "spend_request",
  "related_record_id": "spend_...",
  "created_at": "2026-05-17T00:00:00Z"
}
```

Rules:

- Sanitize paths.
- Avoid overwriting files.
- Hash files where practical.
- Link every artifact to a ledger record.
- Archive terms before acting when possible.
- Archive receipts immediately after spend.

## 13. Data Flow: Experiment Review

```text
Experiment records
  ↓
ledger_skill read
  ↓
experiment_reviewer
  ↓
ExperimentReview
  ↓
ledger_skill write
```

Review object:

```json
{
  "experiment_id": "exp_...",
  "spent_usd": 8,
  "revenue_usd": 0,
  "net_usd": -8,
  "outcome": "failed",
  "lessons": [
    "No response from target audience.",
    "Opportunity requires better validation before spend."
  ],
  "decision": "stop",
  "future_policy_adjustments": []
}
```

Rules:

- Every executed experiment needs a review.
- Failed experiments must record why they failed.
- Repeated failed categories should be downgraded or blocked.
- Successful experiments should still record risks and next limits.

## 14. Database Architecture

Recommended SQLite file:

```text
data/moneybot.sqlite3
```

Recommended tables:

```text
opportunities
policy_decisions
tos_legal_checks
budget_plans
experiments
spend_requests
wallet_transactions
email_drafts
email_events
evidence_artifacts
experiment_reviews
daily_limits
audit_log
```

### 14.1 `opportunities`

Fields:

```text
id
name
category
source_url
summary
required_spend_usd
estimated_revenue_usd
max_loss_usd
legal_risk
tos_risk
status
created_at
updated_at
raw_json
```

### 14.2 `policy_decisions`

Fields:

```text
id
related_record_type
related_record_id
action_type
decision
risk_level
blocked_reasons_json
required_mitigations_json
notes
created_at
raw_json
```

### 14.3 `tos_legal_checks`

Fields:

```text
id
opportunity_id
allowed
confidence
platform_terms_summary
red_flags_json
required_records_json
final_recommendation
created_at
raw_json
```

### 14.4 `budget_plans`

Fields:

```text
id
opportunity_id
experiment_name
spend_required_usd
max_loss_usd
expected_revenue_usd
break_even_condition
success_metric
stop_condition
recommended_budget_usd
decision
created_at
raw_json
```

### 14.5 `experiments`

Fields:

```text
id
opportunity_id
budget_plan_id
status
started_at
ended_at
success_metric
stop_condition
notes
created_at
updated_at
```

### 14.6 `spend_requests`

Fields:

```text
id
experiment_id
budget_plan_id
policy_decision_id
amount_usd_estimate
amount_btc_requested
destination_address
counterparty
purpose
category
status
created_at
updated_at
raw_json
```

### 14.7 `wallet_transactions`

Fields:

```text
id
spend_request_id
txid
amount_btc
fee_btc
amount_usd_estimate
status
sent_at
confirmed_at
raw_json
```

### 14.8 `email_drafts`

Fields:

```text
id
opportunity_id
experiment_id
to_address
subject
body
mode
status
created_at
raw_json
```

### 14.9 `evidence_artifacts`

Fields:

```text
id
artifact_type
path
sha256
source_url
related_record_type
related_record_id
created_at
notes
```

### 14.10 `experiment_reviews`

Fields:

```text
id
experiment_id
spent_usd
revenue_usd
net_usd
outcome
decision
lessons_json
future_policy_adjustments_json
created_at
raw_json
```

### 14.11 `audit_log`

Fields:

```text
id
event_type
actor
related_record_type
related_record_id
message
created_at
raw_json
```

## 15. API Architecture

### 15.1 Wallet Governor API

Suggested local API:

```text
GET  /health
GET  /balance
GET  /limits
POST /quote-spend
POST /send-small-payment
GET  /transactions/{txid}
```

`POST /quote-spend` should not spend. It should estimate BTC amount and fees.

`POST /send-small-payment` should enforce all limits and then perform the payment.

### 15.2 Ledger API

A separate API is optional. If used:

```text
GET  /health
POST /opportunities
POST /policy-decisions
POST /tos-legal-checks
POST /budget-plans
POST /spend-requests
POST /wallet-transactions
POST /email-drafts
POST /evidence-artifacts
POST /experiment-reviews
GET  /experiments/{id}
GET  /audit-log
```

The ledger API should be local-only and schema-validated.

### 15.3 Email Governor API

Optional for later versions:

```text
GET  /health
POST /draft
POST /send-approved
GET  /threads
GET  /limits
```

v1 should not require email sending.

## 16. Schema Strategy

Use strict schemas for every skill output.

Recommended approach:

- Define Pydantic models or equivalent.
- Validate all LLM JSON.
- Store raw JSON after validation.
- Reject unknown required fields.
- Fail closed on missing required fields.
- Record validation failures in audit log.

Examples of shared enums:

```text
PolicyDecision: allow | block | needs_review
RiskLevel: low | medium | high
BudgetDecision: reject | simulate | execute
ExperimentDecision: continue | stop | retry_with_changes | block_category
EmailMode: draft_only | capped_send
SpendStatus: proposed | approved | sent | failed | rejected
```

## 17. Error Handling Strategy

Errors should be explicit and typed.

Examples:

```text
PolicyBlockedError
SchemaValidationError
LedgerWriteError
EvidenceArchiveError
WalletLimitExceededError
WalletServiceUnavailableError
WalletPaymentRejectedError
EmailPolicyViolationError
TermsUnavailableError
HumanReviewRequiredError
```

Default behavior:

- If policy check fails: block action.
- If schema validation fails: block action.
- If ledger write fails: block action.
- If evidence archive fails before a required action: block action or require review.
- If wallet governor fails: do not retry blindly.
- If email governor fails: do not retry blindly.
- If source terms are unavailable: require review.

## 18. Testing Architecture

### 18.1 Unit Tests

Unit tests should cover:

- Policy classification.
- Blocked categories.
- Unknown category handling.
- Budget calculations.
- Ledger insert/read behavior.
- Evidence archive path sanitization.
- Wallet-governor client request validation.
- Email draft validation.
- Experiment review calculations.

### 18.2 Integration Tests

Integration tests should cover:

- End-to-end dry run with no spend.
- End-to-end mocked wallet spend.
- Blocked wallet spend due to missing policy.
- Blocked wallet spend due to limit exceeded.
- Blocked email send due to policy violation.
- Evidence archive linked to ledger record.
- Experiment review generated from ledger data.

### 18.3 No-Mock Preference

Where practical, use real SQLite databases in temporary directories instead of mocking persistence. For wallet and external network behavior, use local fake services rather than real external services in unit tests.

### 18.4 Safety Regression Tests

Create fixtures for bad actions:

```text
crypto trading proposal
prediction market proposal
gambling proposal
fake review proposal
spam outreach proposal
KYC evasion proposal
money transmission proposal
scraping-against-terms proposal
send-all wallet proposal
missing ledger prewrite spend proposal
```

Each must be blocked.

## 19. Configuration Architecture

Suggested config files:

```text
config/moneybot.policy.yaml
config/wallet_governor.yaml
config/email_governor.yaml
config/ledger.yaml
config/archive.yaml
```

Example policy config:

```yaml
blocked_categories:
  - gambling
  - prediction_market
  - securities_trading
  - options_trading
  - forex_trading
  - crypto_trading
  - defi
  - nft_trading
  - money_transmission
  - mixing
  - kyc_evasion
  - fake_accounts
  - fake_reviews
  - spam
  - phishing
  - malware
  - credential_theft

unknown_category_default: needs_review
require_policy_for_spend: true
require_policy_for_email_send: true
require_policy_for_browser_submit: true
```

Example wallet config:

```yaml
wallet:
  asset: BTC
  network: mainnet
  max_wallet_balance_usd: 125
  max_single_payment_usd: 10
  max_daily_payment_usd: 20
  max_weekly_payment_usd: 40
  block_send_all: true
  require_purpose: true
  require_counterparty: true
  require_policy_approval: true
  require_budget_plan: true
  require_ledger_entry_before_send: true
```

Secrets must not be stored in OpenClaw-readable config files.

## 20. Deployment Architecture

Recommended deployment services:

```text
bitcoind.service
openclaw.service
wallet-governor.service
```

Optional:

```text
ledger-api.service
email-governor.service
local-llm.service
```

Recommended service properties:

- Run as non-root.
- Use `NoNewPrivileges=true`.
- Use restricted filesystem permissions.
- Bind local APIs to `127.0.0.1`.
- Keep secrets in root-owned env files readable only by service user.
- Use systemd restart policies carefully.
- Avoid auto-retrying spend operations.

## 21. Workspace Architecture

Suggested directories:

```text
/opt/openclaw-moneybot/
  config/
  skills/
  plugins/
  src/
  scripts/

/var/lib/openclaw-moneybot/
  data/
    moneybot.sqlite3
  archive/
  runs/
  logs/

/var/lib/bitcoind/.bitcoin/
  Bitcoin Core datadir
```

Permissions:

- `/var/lib/bitcoind/.bitcoin/` owned by `bitcoin`.
- `/var/lib/openclaw-moneybot/` owned by `openclawbot` or a dedicated service group.
- Wallet-governor secrets not readable by `openclawbot`.
- LLM prompts and logs must not include wallet secrets.

## 22. Run Lifecycle

A normal run should look like this:

1. Start run record.
2. Load mission.
3. Run opportunity discovery.
4. Store opportunities.
5. Run policy checks.
6. Store policy decisions.
7. Run TOS/legal checks.
8. Store legal/TOS results.
9. Run budget planning.
10. Store budget plans.
11. Choose approved experiment.
12. Create experiment record.
13. Draft required communications.
14. Archive drafts.
15. Request wallet quote if spend is needed.
16. Create spend request.
17. Re-run policy check on exact spend.
18. Send through wallet governor only if all gates pass.
19. Archive receipt and tx metadata.
20. Update experiment state.
21. Review experiment at stop condition.
22. Store review.
23. End run record.

## 23. Fail-Closed Rules

The system must fail closed when:

- Policy result is missing.
- Policy result is `block`.
- Policy result is `needs_review` for an executable action.
- TOS/legal result is missing.
- TOS/legal result is `reject` or `human_review` for an executable action.
- Budget plan is missing.
- Budget plan decision is not `execute` for a spend.
- Ledger prewrite fails.
- Evidence archive is required but fails.
- Wallet limits cannot be checked.
- Wallet amount cannot be converted or quoted.
- Destination is malformed.
- Category is unknown and action is spend/send/submit.
- LLM output is invalid.
- Any required ID reference is missing.
- A service returns an ambiguous result.

## 24. Implementation Sequence

### Phase 1: Foundations

Implement:

- Shared schemas.
- Config loader.
- SQLite ledger.
- Audit log.
- Evidence archive.
- Basic policy guard.

Goal:

- Store and retrieve structured records.
- Validate policy outputs.
- Block prohibited fixtures.

### Phase 2: Research Pipeline

Implement:

- Opportunity scout.
- TOS/legal checker.
- Budget planner.
- Experiment records.

Goal:

- Run dry opportunity discovery and planning with no wallet or email execution.

### Phase 3: Review Pipeline

Implement:

- Experiment reviewer.
- Outcome tracking.
- Lessons learned.

Goal:

- Complete a full no-spend experiment loop.

### Phase 4: Wallet Mock

Implement:

- Wallet-governor service in mock mode.
- Wallet-governor client.
- Spend request validation.
- Limit enforcement.

Goal:

- Run full mocked spend flow.

### Phase 5: Real Wallet Test

Implement:

- Bitcoin Core integration.
- Balance check.
- Quote spend.
- Tiny real transaction.
- Transaction ledger write.
- Evidence archive link.

Goal:

- Perform one tiny real wallet test under strict limits.

### Phase 6: Email Drafting

Implement:

- Email drafter in draft-only mode.
- Draft archive.
- Policy checks for email content.

Goal:

- Create and archive approved drafts without sending.

### Phase 7: Optional Email Sending

Implement only if needed:

- Email governor.
- Send limits.
- Thread tracking.
- Incoming reply classification.

Goal:

- Send very limited, policy-approved bot-account emails.

## 25. Future Extensions

Possible later additions:

- Solana USDC wallet governor.
- EVM wallet governor.
- Browser-governor service.
- Product-builder skill.
- Landing-page skill.
- Bounty-finder specialization.
- Pricing-and-fee estimator.
- Tax export reports.
- Human approval dashboard.
- Run comparison dashboard.
- Model output quality evaluator.

Do not add these until the v1 safety and ledger pipeline is reliable.

## 26. Architecture Summary

The architecture intentionally separates reasoning from authority.

The LLM can suggest. Skills can structure. Validators can verify. Governors can enforce. The ledger records. The archive preserves proof. The wallet service executes only tiny approved payments.

That separation is the core safety property of OpenClaw MoneyBot.
