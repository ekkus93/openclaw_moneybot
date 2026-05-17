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

# TODO — Ledger API Service

## Goal

Optionally expose the SQLite ledger through a narrow local API so OpenClaw skills can record and query audit data without direct database file access.

## Implementation tasks

### 1. Service scaffold

- [ ] Create `plugins/ledger-api/` service directory.
- [ ] Use a small local HTTP API or direct Python module depending on OpenClaw integration style.
- [ ] Keep service bound to `127.0.0.1`.
- [ ] Configure DB path through a service config file.
- [ ] Fail closed if database migrations are not current.

### 2. Endpoints or module functions

- [ ] Create opportunity record.
- [ ] Record policy decision.
- [ ] Record TOS/legal check.
- [ ] Record budget plan.
- [ ] Record spend request.
- [ ] Record transaction result.
- [ ] Record evidence.
- [ ] Record email draft.
- [ ] Record experiment review.
- [ ] Query opportunity timeline.
- [ ] Query daily/weekly spend totals.
- [ ] Export accounting CSV.

### 3. Security and integrity

- [ ] Restrict all writes to known schemas.
- [ ] Reject arbitrary SQL.
- [ ] Enforce idempotency keys.
- [ ] Preserve event hash chain.
- [ ] Log safe audit metadata.
- [ ] Do not store secrets.

### 4. Tests

- [ ] Test every endpoint/function.
- [ ] Test malformed request rejection.
- [ ] Test idempotency.
- [ ] Test hash chain verification.
- [ ] Test spend total queries.
- [ ] Test export output.

### 5. Acceptance criteria

- [ ] Skills can record all required audit data.
- [ ] Wallet-governor can verify pre-written spend records.
- [ ] The ledger remains append-oriented and tamper-evident.
