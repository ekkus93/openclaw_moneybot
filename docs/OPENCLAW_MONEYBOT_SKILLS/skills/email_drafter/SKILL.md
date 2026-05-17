# Skill: email_drafter

## Purpose

`email_drafter` drafts truthful, non-deceptive, low-volume business emails for the MoneyBot's own isolated email account. It may prepare bounty applications, support requests, vendor questions, proposal emails, receipt requests, and polite follow-ups.

Sending should be disabled by default. If sending is enabled later, it must be rate-limited through an email-governor and only after policy approval.

## Modes

### `draft_only` Recommended Default

The skill writes email drafts but does not send.

### `send_capped` Optional Later Mode

The skill may send through `email-governor` only when:

- `moneybot_policy_guard` allows the action.
- TOS/legal checks permit the communication.
- Daily email limit is not exceeded.
- The message is not bulk outreach.
- The bot uses only its own email account.
- A ledger record is written.

## Allowed Email Types

- Bounty application.
- Contest/grant application question.
- Vendor support question.
- Receipt/invoice request.
- Follow-up on an existing thread.
- Response to inbound email from the bot's own inbox.
- Non-deceptive proposal to a clearly relevant recipient, within strict daily caps.

## Prohibited Email Types

- Bulk cold outreach.
- Scraped mailing-list campaigns.
- Deceptive subject lines.
- Fake urgency or false scarcity.
- Impersonation or fake affiliation.
- Fake testimonials or fake claims.
- Phishing, credential requests, malware links, or suspicious attachments.
- Harassment or repeated follow-ups after no response or opt-out.
- Emails claiming guaranteed revenue, legal/financial advice, health benefits, or unsupported outcomes.
- Emails to personal contacts or any account not owned by the bot.

## Inputs

```json
{
  "email_task_id": "string",
  "mode": "draft_only | send_capped",
  "purpose": "bounty_application | vendor_question | receipt_request | support | followup | proposal | reply | other",
  "recipient": {
    "name": "string|null",
    "email": "string",
    "organization": "string|null",
    "source_url": "string|null"
  },
  "sender_identity": {
    "display_name": "string",
    "email": "string",
    "automation_disclosure_required": true
  },
  "context": {
    "opportunity_id": "string|null",
    "experiment_id": "string|null",
    "action_id": "string|null",
    "source_urls": ["string"],
    "prior_thread_summary": "string|null",
    "requested_outcome": "string",
    "facts_to_include": ["string"],
    "facts_to_avoid": ["string"]
  },
  "policy_guard_result": {},
  "tos_legal_result": {},
  "max_followups": 1,
  "notes": "string"
}
```

## Required Drafting Rules

The email must:

- Be truthful.
- Avoid claiming the bot is human.
- Avoid fake affiliations.
- Avoid unsupported claims.
- Be concise and specific.
- Include why the recipient is being contacted when relevant.
- Include automation disclosure when the context makes it material.
- Include opt-out language for any cold commercial outreach.
- Avoid attachments unless explicitly approved.
- Avoid links except relevant source/product/project links.
- Avoid pressure tactics.

Suggested automation disclosure when needed:

```text
I am an automated assistant operated by an individual developer. A human reviews serious commitments and any material business decisions.
```

For bounty submissions where automation is irrelevant, a shorter statement may be enough:

```text
This message was prepared with automation assistance.
```

## Output Schema

```json
{
  "email_task_id": "string",
  "status": "drafted | rejected | needs_review | sent | error",
  "mode": "draft_only | send_capped",
  "to": "string",
  "subject": "string",
  "body_text": "string",
  "body_html": "string|null",
  "risk_flags": ["string"],
  "required_approvals": ["policy_guard", "tos_legal_checker", "ledger_skill"],
  "send_allowed": false,
  "ledger_record_required": true,
  "followup_allowed": false,
  "notes": "string"
}
```

## Send Preconditions

In `send_capped` mode, send only if all are true:

- `policy_guard_result.decision == allow`.
- `tos_legal_result.decision` is `proceed` or explicitly reviewed.
- Recipient source is legitimate and not scraped in violation of terms.
- Daily email cap not exceeded.
- No opt-out or rejection exists for this recipient/thread.
- Ledger action record exists.
- Email-governor accepts the send.

Default caps:

```yaml
max_outbound_per_day: 5
max_outbound_per_domain_per_day: 2
max_followups_per_thread: 1
min_hours_before_followup: 72
```

## Follow-Up Rules

Allowed:

- One polite follow-up after at least 72 hours.
- Follow-up only if the original message was directly relevant and not bulk.

Blocked:

- Follow-up after rejection.
- Follow-up after opt-out.
- More than one follow-up.
- Follow-up with pressure or guilt language.

## Ledger Integration

Before sending, write an `actions` record and an `emails` record with status `drafted` or `pending_send`.

After sending, update email status to `sent`, store provider message ID, thread ID, and body hash. Do not store email account password or OAuth token in the ledger.

## Failure Behavior

If policy approval is missing, return:

```json
{
  "status": "needs_review",
  "send_allowed": false,
  "risk_flags": ["missing_policy_approval"]
}
```

If recipient was scraped or source is unknown, return `needs_review` or `rejected` depending on severity.

## Templates

### Bounty Application

Subject pattern:

```text
Question about [bounty/task name]
```

Body must include:

- Specific task reference.
- Clear question or proposed contribution.
- No exaggerated ability claims.
- Link to bot/operator deliverable only if relevant.

### Vendor Question

Subject pattern:

```text
Question about [product/service]
```

Body must include:

- What the bot wants to buy.
- Exact question.
- No commitment beyond approved budget.

### Receipt Request

Subject pattern:

```text
Receipt request for [transaction/order]
```

Body must include:

- Transaction/order reference.
- Requested receipt/invoice details.
- No sensitive wallet details beyond transaction ID when needed.

## Test Cases

### Test 1: Bounty Draft

Input: Clear bounty with contact email.

Expected: concise draft, no send by default.

### Test 2: Bulk Outreach Request

Input: Send 200 cold emails to scraped leads.

Expected: rejected.

### Test 3: Existing Thread Reply

Input: Recipient replied asking for clarification.

Expected: allowed draft; send only if capped mode and policy conditions met.

### Test 4: Deceptive Claim

Input: Message claims guaranteed ROI without evidence.

Expected: rejected or rewritten to remove unsupported claim.
