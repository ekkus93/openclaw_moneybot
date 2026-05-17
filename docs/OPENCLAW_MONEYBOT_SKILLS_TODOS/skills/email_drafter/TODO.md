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

# TODO — `email_drafter`

## Goal

Implement draft-only business email generation for opportunities, applications, support requests, receipts, and follow-ups. This skill should not send email in v1. It must avoid spam, deception, fake identity, and misleading commercial claims.

## Implementation tasks

### 1. Skill scaffolding

- [ ] Create implementation module for `email_drafter`.
  - [ ] `models.py` for Pydantic v2 contracts.
  - [ ] `templates.py` for safe reusable email templates.
  - [ ] `compliance.py` for anti-spam/deception checks.
  - [ ] `runner.py` for OpenClaw entrypoint.
- [ ] Add tests under `tests/skills/test_email_drafter.py`.

### 2. Input contract

- [ ] Define `EmailDraftRequest`.
  - [ ] `opportunity_id`
  - [ ] `purpose`
  - [ ] `recipient_name`
  - [ ] `recipient_email`
  - [ ] `recipient_organization`
  - [ ] `context_summary`
  - [ ] `source_url`
  - [ ] `policy_decision_id`
  - [ ] `tos_legal_check_id`
  - [ ] `allowed_claims`
  - [ ] `forbidden_claims`
  - [ ] `tone`
  - [ ] `requested_call_to_action`
- [ ] Require policy decision for outbound commercial/contact email.
- [ ] Require source/context for bounty/application email.
- [ ] Reject mass-recipient requests.
- [ ] Reject missing recipient for direct emails.

### 3. Output contract

- [ ] Define `EmailDraftResult`.
  - [ ] `email_draft_id`
  - [ ] `mode`: always `draft` in v1.
  - [ ] `to`
  - [ ] `subject`
  - [ ] `body`
  - [ ] `risk_flags`
  - [ ] `compliance_notes`
  - [ ] `requires_human_review`
  - [ ] `ledger_record`
  - [ ] `evidence_archive_ids`
- [ ] Include template name and version.
- [ ] Include generated timestamp.

### 4. Email types

- [ ] Implement bounty/application submission draft.
- [ ] Implement polite business inquiry draft.
- [ ] Implement support/request-for-clarification draft.
- [ ] Implement receipt/invoice request draft.
- [ ] Implement one-time follow-up draft.
- [ ] Implement rejection/withdrawal draft.
- [ ] Implement payout confirmation draft.

### 5. Safety/compliance checks

- [ ] Block deceptive identity.
- [ ] Block pretending to be a human if the bot is representing itself.
- [ ] Block fake affiliation.
- [ ] Block fake urgency/scarcity.
- [ ] Block unsupported earnings claims.
- [ ] Block fake testimonials or reviews.
- [ ] Block scraped-list/mass email use.
- [ ] Block harassment or repeated follow-up loops.
- [ ] Require clear, accurate subject lines.
- [ ] Require truthful description of who operates the bot/account.
- [ ] Require opt-out language for cold commercial outreach if such outreach is ever permitted.

### 6. Template quality

- [ ] Keep drafts concise.
- [ ] Include context-specific reason for contact.
- [ ] Avoid aggressive sales language.
- [ ] Avoid overpromising.
- [ ] Include exact next action.
- [ ] Preserve facts from source context without invention.
- [ ] Mark uncertain facts as placeholders or ask for review.

### 7. Ledger/evidence integration

- [ ] Archive generated draft body hash and content file.
- [ ] Record draft in `email_records` table.
- [ ] Link draft to opportunity, policy decision, TOS check, and evidence.
- [ ] Do not send email directly.
- [ ] Create a handoff object for future email-governor service only if enabled.

### 8. Tests

- [ ] Test each email type renders.
- [ ] Test mass-recipient input is rejected.
- [ ] Test deceptive identity claim is blocked.
- [ ] Test unsupported earning claim is flagged.
- [ ] Test missing policy decision blocks cold outreach draft.
- [ ] Test subject is non-empty and non-deceptive.
- [ ] Test draft output is ledger-ready.
- [ ] Test no send operation occurs.

### 9. Acceptance criteria

- [ ] The skill produces drafts only.
- [ ] The skill refuses spam/deceptive/mass outreach patterns.
- [ ] Every draft is tied to a real opportunity/context.
- [ ] Every draft is archived and ledger-recordable.
