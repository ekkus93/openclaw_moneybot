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

# TODO — `receipt_and_evidence_archiver`

## Goal

Implement the evidence-capture layer for opportunity pages, rules/TOS pages, invoices, receipts, wallet transaction metadata, email drafts, submitted deliverables, payout proof, and experiment reviews.

## Implementation tasks

### 1. Skill scaffolding

- [ ] Create implementation module for `receipt_and_evidence_archiver`.
  - [ ] `models.py` for Pydantic v2 contracts.
  - [ ] `storage.py` for local file storage.
  - [ ] `hashing.py` for SHA-256 content hashes.
  - [ ] `runner.py` for OpenClaw entrypoint.
- [ ] Add tests under `tests/skills/test_receipt_and_evidence_archiver.py`.

### 2. Storage layout

- [ ] Create base archive directory from config.
- [ ] Create subdirectories by date.
- [ ] Create subdirectories by opportunity ID.
- [ ] Store metadata JSON beside every archived item.
- [ ] Store source content as immutable files.
- [ ] Never overwrite existing evidence files.
- [ ] Use content hash or UUID file names.

Example layout:

```text
archive/
  2026/05/17/
    opportunity_<id>/
      evidence_<id>.metadata.json
      evidence_<id>.html
      evidence_<id>.txt
      evidence_<id>.png
      evidence_<id>.json
```

### 3. Input contract

- [ ] Define `EvidenceArchiveRequest`.
  - [ ] `related_type`
  - [ ] `related_id`
  - [ ] `evidence_type`
  - [ ] `source_url`
  - [ ] `content_text`
  - [ ] `content_bytes_path`
  - [ ] `mime_type`
  - [ ] `captured_at`
  - [ ] `notes`
- [ ] Validate related type and ID.
- [ ] Require either content text, file path, or source URL snapshot payload.
- [ ] Reject unsafe paths.
- [ ] Normalize evidence types.

### 4. Output contract

- [ ] Define `EvidenceArchiveResult`.
  - [ ] `evidence_id`
  - [ ] `related_type`
  - [ ] `related_id`
  - [ ] `evidence_type`
  - [ ] `archive_path`
  - [ ] `metadata_path`
  - [ ] `content_sha256`
  - [ ] `source_url`
  - [ ] `created_at`
  - [ ] `ledger_record`
- [ ] Include storage version.
- [ ] Include file size.

### 5. Evidence types

- [ ] Support opportunity source page.
- [ ] Support TOS/rules page.
- [ ] Support budget plan snapshot.
- [ ] Support policy decision snapshot.
- [ ] Support email draft.
- [ ] Support invoice/payment request.
- [ ] Support receipt.
- [ ] Support BTC transaction metadata.
- [ ] Support submitted deliverable.
- [ ] Support payout proof.
- [ ] Support experiment review snapshot.

### 6. Browser/page capture integration

- [ ] Accept captured HTML from browser tool.
- [ ] Accept extracted text from browser tool.
- [ ] Accept screenshot path if browser tool provides one.
- [ ] Record retrieval timestamp.
- [ ] Record final URL after redirects.
- [ ] Record page title if available.
- [ ] Do not fetch remote pages directly unless the skill is explicitly granted browser/network access.

### 7. Hashing and integrity

- [ ] Calculate SHA-256 for every stored content file.
- [ ] Store hash in metadata.
- [ ] Add verification function.
- [ ] Test that changed evidence files fail verification.
- [ ] Link evidence record hash to ledger event.

### 8. Privacy and secret handling

- [ ] Redact wallet passphrases if accidentally present.
- [ ] Redact private keys/seed phrases if accidentally present.
- [ ] Redact authentication cookies/tokens if browser captures include them.
- [ ] Add redaction markers to metadata.
- [ ] Never silently discard redaction events; record them.

### 9. Ledger integration

- [ ] Write evidence records to ledger.
- [ ] Link evidence IDs to related opportunity/policy/budget/spend/email records.
- [ ] Support retrieving evidence list by opportunity ID.
- [ ] Support exporting evidence manifest.

### 10. Tests

- [ ] Test text evidence archival.
- [ ] Test file evidence archival.
- [ ] Test immutable no-overwrite behavior.
- [ ] Test metadata correctness.
- [ ] Test content hash verification.
- [ ] Test unsafe path rejection.
- [ ] Test secret redaction.
- [ ] Test ledger-ready output.

### 11. Acceptance criteria

- [ ] Every important MoneyBot decision/action can attach evidence.
- [ ] Evidence is immutable and hash-verifiable.
- [ ] Evidence records link back to ledger records.
- [ ] Secret material is redacted if accidentally captured.
