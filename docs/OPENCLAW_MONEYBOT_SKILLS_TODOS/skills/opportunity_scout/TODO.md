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

# TODO — `opportunity_scout`

## Goal

Implement a research-only skill that finds legal, low-capital opportunities for the bot to pursue. It must not spend money, send emails, create accounts, fill forms, or make commitments.

## Implementation tasks

### 1. Skill scaffolding

- [ ] Create implementation module for `opportunity_scout`.
  - [ ] `models.py` for Pydantic v2 contracts.
  - [ ] `sources.py` for opportunity source definitions.
  - [ ] `scoring.py` for deterministic ranking.
  - [ ] `dedupe.py` for duplicate detection.
  - [ ] `runner.py` for the OpenClaw entrypoint.
- [ ] Add tests under `tests/skills/test_opportunity_scout.py`.
- [ ] Make all unit tests work with local fixture HTML/JSON, not live browsing.

### 2. Define source categories

- [ ] Create source registry for opportunity types.
  - [ ] Paid open-source bounties.
  - [ ] Documentation bounties.
  - [ ] Hackathons/contests with clear rules.
  - [ ] Small freelance gigs.
  - [ ] Grants with clear eligibility.
  - [ ] Micro-product ideas based on public non-personal market signals.
  - [ ] Legit affiliate programs only if no spam/deception is required.
- [ ] Add source-level metadata.
  - [ ] Source name.
  - [ ] URL.
  - [ ] Expected payment method.
  - [ ] Rules/TOS URL if available.
  - [ ] Known risk notes.
- [ ] Mark unsupported source categories.
  - [ ] Trading.
  - [ ] Gambling.
  - [ ] Prediction markets.
  - [ ] Airdrop farming.
  - [ ] Fake-account schemes.
  - [ ] Grey-market arbitrage.

### 3. Input contract

- [ ] Define `OpportunityScoutRequest`.
  - [ ] `mission`
  - [ ] `budget_usd`
  - [ ] `skills_available`
  - [ ] `blocked_categories`
  - [ ] `preferred_categories`
  - [ ] `max_results`
  - [ ] `time_budget_hours`
  - [ ] `evidence_required`
- [ ] Validate `budget_usd <= configured max budget`.
- [ ] Default `max_results` to a safe bounded number.
- [ ] Reject requests that ask for prohibited source categories.

### 4. Output contract

- [ ] Define `OpportunityCandidate`.
  - [ ] `opportunity_id`
  - [ ] `name`
  - [ ] `category`
  - [ ] `source_url`
  - [ ] `rules_url`
  - [ ] `payment_or_revenue_mechanism`
  - [ ] `required_spend_usd`
  - [ ] `estimated_time_hours`
  - [ ] `estimated_revenue_usd`
  - [ ] `max_loss_usd`
  - [ ] `legal_risk_precheck`
  - [ ] `tos_risk_precheck`
  - [ ] `evidence_links`
  - [ ] `recommended_next_skill`
- [ ] Define `OpportunityScoutResult`.
  - [ ] `candidates`
  - [ ] `rejected_candidates`
  - [ ] `search_summary`
  - [ ] `source_coverage`
  - [ ] `next_actions`
- [ ] Ensure all candidates are marked as `unverified` until checked by `tos_legal_checker` and `moneybot_policy_guard`.

### 5. Search and extraction

- [ ] Implement fixture-based extraction first.
- [ ] Implement live browser/search integration only behind OpenClaw tool boundaries.
- [ ] Extract candidate title, source URL, compensation, rules URL, deadline, and required steps.
- [ ] Do not scrape sites that disallow automated access.
- [ ] Do not login to any site from this skill.
- [ ] Do not submit applications or messages from this skill.
- [ ] Capture enough source text to support later TOS/legal review.

### 6. Deduplication

- [ ] Deduplicate by canonical URL.
- [ ] Deduplicate by normalized title/source pair.
- [ ] Deduplicate by fuzzy title similarity for near-identical listings.
- [ ] Keep the highest-quality evidence source when duplicates are found.
- [ ] Record duplicate count in output.

### 7. Risk pre-filtering

- [ ] Pre-filter obvious prohibited categories before scoring.
- [ ] Reject anything that appears to require:
  - [ ] Trading or speculation.
  - [ ] Gambling or prediction markets.
  - [ ] Fake accounts or KYC evasion.
  - [ ] Spam outreach.
  - [ ] Handling other people's funds.
  - [ ] Malware/exploit deployment outside explicit legal bug bounty scope.
- [ ] Mark unclear items as `needs_tos_legal_check`, not `recommended`.
- [ ] Always include the reason for rejection.

### 8. Scoring and ranking

- [ ] Implement deterministic scoring.
  - [ ] Low required spend increases score.
  - [ ] Clear payment mechanism increases score.
  - [ ] Clear rules/TOS increases score.
  - [ ] Low legal/TOS risk increases score.
  - [ ] High time-to-first-dollar reduces score.
  - [ ] Unclear counterparty reduces score.
  - [ ] Missing rules URL reduces score.
- [ ] Produce sub-scores.
  - [ ] `legitimacy_score`
  - [ ] `fit_score`
  - [ ] `roi_score`
  - [ ] `risk_score`
  - [ ] `evidence_score`
- [ ] Document score formula in code comments or README.

### 9. Handoff integration

- [ ] For every top candidate, generate a handoff request to `tos_legal_checker`.
- [ ] Do not mark a candidate executable until TOS/legal and policy checks pass.
- [ ] Add ledger-ready opportunity discovery record.
- [ ] Link evidence archive IDs if evidence was captured.

### 10. Tests

- [ ] Test safe opportunity extraction from fixture pages.
- [ ] Test prohibited opportunity rejection.
- [ ] Test duplicate detection.
- [ ] Test scoring order.
- [ ] Test missing rules URL reduces score.
- [ ] Test no wallet/email/browser-submit calls are made.
- [ ] Test output schema validation.
- [ ] Test handoff object for `tos_legal_checker`.

### 11. Acceptance criteria

- [ ] Skill can produce at least 20 ranked candidates from fixtures.
- [ ] Skill cannot execute or commit to any opportunity.
- [ ] Every candidate includes source evidence.
- [ ] Every recommended candidate has a downstream TOS/legal check requirement.
- [ ] Prohibited categories are filtered before ranking.
