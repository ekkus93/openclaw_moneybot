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

# TODO — `tos_legal_checker`

## Goal

Implement the rules, terms, and legal-risk review skill. It should evaluate whether a proposed opportunity or action appears permitted by applicable platform rules and whether it triggers obvious legal/regulated-activity risks. It must fail closed when uncertain.

## Implementation tasks

### 1. Skill scaffolding

- [ ] Create implementation module for `tos_legal_checker`.
  - [ ] `models.py` for contracts.
  - [ ] `extract.py` for rules/TOS page extraction.
  - [ ] `analysis.py` for deterministic risk analysis.
  - [ ] `runner.py` for OpenClaw entrypoint.
- [ ] Add tests under `tests/skills/test_tos_legal_checker.py`.
- [ ] Add fixture pages for acceptable, ambiguous, and prohibited opportunities.

### 2. Input contract

- [ ] Define `TosLegalCheckRequest`.
  - [ ] `opportunity_id`
  - [ ] `opportunity_name`
  - [ ] `source_url`
  - [ ] `rules_url`
  - [ ] `proposed_action`
  - [ ] `platform_name`
  - [ ] `counterparty`
  - [ ] `spend_amount_usd`
  - [ ] `expected_revenue_usd`
  - [ ] `evidence_text`
  - [ ] `evidence_archive_ids`
- [ ] Require at least one source of rules/evidence.
- [ ] Validate URLs if present.
- [ ] Reject empty proposed actions.

### 3. Output contract

- [ ] Define `TosLegalCheckResult`.
  - [ ] `decision`: `proceed | reject | human_review`
  - [ ] `confidence`: `low | medium | high`
  - [ ] `platform_terms_summary`
  - [ ] `legal_risk_summary`
  - [ ] `tos_risk_summary`
  - [ ] `red_flags`
  - [ ] `required_mitigations`
  - [ ] `required_records`
  - [ ] `source_quotes_or_snippets`
  - [ ] `evidence_archive_ids`
  - [ ] `handoff_to_policy_guard`
- [ ] Include `checker_version`.
- [ ] Include timestamp.
- [ ] Include stable result ID.

### 4. Rules/TOS evidence extraction

- [ ] Implement local text extraction for saved HTML/Markdown/PDF text fixtures.
- [ ] Extract sections likely relevant to:
  - [ ] Eligibility.
  - [ ] Payment terms.
  - [ ] Prohibited conduct.
  - [ ] Automation/bot restrictions.
  - [ ] Spam/outreach restrictions.
  - [ ] Account rules.
  - [ ] Data collection/privacy rules.
  - [ ] Refund/cancellation rules.
  - [ ] Deadlines and submission requirements.
- [ ] Preserve source URL and extraction timestamp.
- [ ] Send extracted source material to `receipt_and_evidence_archiver` if not already archived.
- [ ] Avoid over-quoting; store full source in archive instead of repeating it in decision text.

### 5. Deterministic risk checks

- [ ] Add hard reject rules.
  - [ ] Terms prohibit bots/automation and action requires automation.
  - [ ] Terms prohibit commercial use and action is commercial.
  - [ ] Opportunity requires fake accounts.
  - [ ] Opportunity requires deceptive identity.
  - [ ] Opportunity requires spam/mass outreach.
  - [ ] Opportunity requires handling other people's funds.
  - [ ] Opportunity involves gambling/prediction/trading.
  - [ ] Payment mechanism is unclear or suspicious.
- [ ] Add human-review rules.
  - [ ] Rules page unavailable.
  - [ ] Rules are ambiguous.
  - [ ] Platform requires identity verification.
  - [ ] Action involves recurring billing.
  - [ ] Action involves user data collection.
  - [ ] Action involves public claims, advertising, or affiliate marketing.
- [ ] Add proceed rules only when evidence is clear and low-risk.

### 6. Legal-risk heuristics

- [ ] Identify regulated-finance indicators.
  - [ ] Exchange.
  - [ ] Broker.
  - [ ] Escrow.
  - [ ] Funds transfer.
  - [ ] Investment advice.
  - [ ] Yield/interest.
  - [ ] Securities/options/forex.
- [ ] Identify consumer-protection indicators.
  - [ ] Earnings claims.
  - [ ] Health claims.
  - [ ] Fake scarcity.
  - [ ] Misleading affiliation.
  - [ ] Deceptive testimonials.
- [ ] Identify privacy/data indicators.
  - [ ] Collecting emails.
  - [ ] Tracking users.
  - [ ] Storing personal data.
  - [ ] Selling data.
- [ ] Return `human_review` or `reject` for these based on severity.

### 7. Handoff integration

- [ ] Produce a `PolicyCheckRequest` for `moneybot_policy_guard`.
- [ ] Include extracted red flags as policy metadata.
- [ ] Include required mitigations that must be satisfied before execution.
- [ ] Record result in `ledger_skill`.
- [ ] Link all relevant evidence archive IDs.

### 8. Tests

- [ ] Test clear allowed bounty fixture -> `proceed`.
- [ ] Test automation prohibited fixture -> `reject`.
- [ ] Test missing rules URL -> `human_review`.
- [ ] Test fake-account requirement -> `reject`.
- [ ] Test unclear payment terms -> `human_review`.
- [ ] Test affiliate marketing terms with spam restriction -> requires mitigation.
- [ ] Test regulated-finance language -> `reject` or `human_review`.
- [ ] Test output includes evidence references.
- [ ] Test handoff to policy guard is valid.

### 9. Acceptance criteria

- [ ] No action can be marked `proceed` without clear supporting evidence.
- [ ] Missing or ambiguous rules never produce `proceed`.
- [ ] The output is structured, auditable, and linked to archived evidence.
- [ ] The skill works offline with fixtures.
