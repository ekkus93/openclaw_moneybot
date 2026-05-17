# Skill: receipt_and_evidence_archiver

## Purpose

`receipt_and_evidence_archiver` captures, stores, hashes, summarizes, and links evidence for every important MoneyBot opportunity, decision, spend, email, submission, receipt, and outcome.

The bot must not rely only on memory or transient web pages. Evidence must be stored locally and linked to ledger records.

## What To Archive

Archive when available:

- Opportunity page.
- Bounty rules or contest rules.
- Terms of service summaries and source pages.
- Privacy policy pages when user data is involved.
- Payment instructions.
- Invoices and receipts.
- Wallet transaction IDs/signatures.
- Screenshots of purchase confirmations.
- Email drafts and sent email bodies.
- Inbound replies relevant to experiment outcome.
- Submitted deliverables.
- Product pages, landing pages, or marketplace listings created by the bot.
- Payout confirmations.
- Experiment review reports.

## Storage Location

Recommended structure:

```text
/opt/openclawbot/data/evidence/
  opportunities/
  terms/
  receipts/
  emails/
  submissions/
  wallet/
  screenshots/
  products/
  reviews/
```

Each archived item should have:

- Local file path.
- SHA-256 hash.
- Timestamp.
- Source URL or origin.
- Related opportunity/action/experiment/spend IDs.
- Short summary.

## Inputs

```json
{
  "archive_task_id": "string",
  "related_ids": {
    "opportunity_id": "string|null",
    "experiment_id": "string|null",
    "action_id": "string|null",
    "spend_request_id": "string|null",
    "wallet_transaction_id": "string|null",
    "email_id": "string|null"
  },
  "artifact_type": "opportunity_page | terms_page | receipt | invoice | email | screenshot | submission | wallet_tx | product | review | other",
  "source_url": "string|null",
  "content_text": "string|null",
  "source_file_path": "string|null",
  "screenshot_required": false,
  "summary_hint": "string|null",
  "notes": "string"
}
```

## Output Schema

```json
{
  "archive_task_id": "string",
  "status": "archived | skipped | error",
  "artifact_id": "string|null",
  "artifact_type": "string",
  "local_path": "string|null",
  "sha256": "string|null",
  "source_url": "string|null",
  "created_at": "ISO-8601 timestamp",
  "summary": "string",
  "ledger_receipt_id": "string|null",
  "errors": [],
  "notes": "string"
}
```

## File Naming

Use deterministic, collision-resistant names:

```text
YYYYMMDDTHHMMSSZ_<artifact_type>_<related_id>_<short_slug>.<ext>
```

Examples:

```text
20260517T170102Z_terms_opp_123_github_bounty_rules.html
20260517T170412Z_receipt_spend_456_domain_purchase.pdf
20260517T170930Z_wallet_tx_spend_456_btc_txid.json
```

## Hashing Requirement

Every local artifact must be hashed with SHA-256 and recorded in `ledger_skill`.

```json
{
  "local_path": "/opt/openclawbot/data/evidence/receipts/...pdf",
  "sha256": "hex-string"
}
```

## Supported Artifact Formats

Preferred:

- `.html` for saved web pages.
- `.txt` or `.eml` for emails.
- `.json` for structured responses.
- `.pdf` for invoices or official documents.
- `.png` for screenshots.
- `.md` for generated summaries and reviews.

Do not store browser cookies, session tokens, passwords, private keys, seed phrases, or wallet passphrases.

## Archival Rules By Artifact Type

### Opportunity Page

Archive:

- URL.
- Page title.
- Relevant summary.
- Date accessed.
- Payment or opportunity details.

### Terms Page

Archive:

- URL.
- Summary of relevant permissions and restrictions.
- Date accessed.
- Link to `tos_checks` ledger record.

### Receipt / Invoice

Archive:

- Vendor.
- Amount.
- Currency.
- Date.
- Order/reference ID.
- Payment method or transaction ID.
- Local file hash.

### Wallet Transaction

Archive:

```json
{
  "chain": "bitcoin | solana | ethereum",
  "asset": "BTC | USDC_SOL | SOL | ETH",
  "txid_or_signature": "string",
  "amount": "string",
  "fee": "string|null",
  "destination": "string",
  "block_or_slot": "string|null",
  "confirmation_status": "string"
}
```

### Email

Archive:

- Subject.
- From/to.
- Timestamp.
- Body hash.
- Body text or `.eml` file if available.
- Thread ID/message ID.

## Integration With Ledger

After successful archive, call `ledger_skill.record_receipt` or equivalent with:

```json
{
  "receipt_type": "string",
  "source_url": "string|null",
  "local_path": "string",
  "sha256": "string",
  "summary": "string",
  "related_ids": {}
}
```

If ledger write fails after archiving, return `error` and include local path so the caller can retry ledger insertion.

## Failure Behavior

If a web page cannot be saved:

- Store a text summary with source URL and failure reason.
- Mark status `archived` only if at least the summary artifact is saved and hashed.
- Otherwise return `error`.

If a screenshot fails:

- Continue with HTML/text capture if available.
- Include screenshot failure in `errors`.

## Privacy and Secret Handling

Before saving artifacts, redact:

- Passwords.
- API keys.
- Wallet seed phrases/private keys/passphrases.
- Session cookies.
- OAuth tokens.
- Personal account credentials.

Do not redact ordinary transaction IDs, public wallet addresses, invoice IDs, or public opportunity URLs unless specifically configured.

## Test Cases

### Test 1: Receipt Archive

Input: PDF receipt path and spend_request_id.

Expected: copy to evidence folder, hash, ledger receipt record created.

### Test 2: Terms Page Archive

Input: terms URL and text summary.

Expected: save HTML or text summary, hash, link to TOS check.

### Test 3: Wallet Transaction Archive

Input: BTC txid and transaction metadata.

Expected: JSON artifact created, hash stored, ledger receipt linked.

### Test 4: Secret Redaction

Input artifact text contains API key or wallet passphrase marker.

Expected: redact before storing or reject archive with critical error.

### Test 5: Web Save Failure

Input URL unavailable but content summary exists.

Expected: save summary artifact with failure note, not silent failure.
