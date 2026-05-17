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

# TODO — Wallet Governor Service

## Goal

Build the separate local service that owns the actual Bitcoin Core wallet interaction. OpenClaw must call this service through `wallet_governor_client`; OpenClaw must not call Bitcoin Core directly.

## Implementation tasks

### 1. Service scaffold

- [ ] Create `plugins/wallet-governor/` service directory.
- [ ] Use a small HTTP framework already acceptable in the repo, or FastAPI if starting new.
- [ ] Add Pydantic v2 request/response models.
- [ ] Add config loader for limits and Bitcoin Core datadir/wallet name.
- [ ] Load wallet passphrase only from root-owned env file or equivalent secure service configuration.
- [ ] Do not expose passphrase through any endpoint or logs.

### 2. Endpoints

- [ ] `GET /health`
- [ ] `GET /balance`
- [ ] `GET /daily-limits`
- [ ] `POST /quote-spend`
- [ ] `POST /send-small-payment`
- [ ] `GET /ledger-summary` if useful.

### 3. Hard safety rules

- [ ] Enforce max single spend.
- [ ] Enforce max daily spend.
- [ ] Enforce max weekly spend.
- [ ] Block send-all.
- [ ] Block prohibited categories.
- [ ] Require policy decision ID.
- [ ] Require budget plan ID.
- [ ] Require ledger spend request ID.
- [ ] Require purpose and counterparty.
- [ ] Require destination address.
- [ ] Reject duplicate idempotency keys unless returning same prior result.
- [ ] Reject repeated payment to same address within configured cooldown unless explicitly allowed.

### 4. Bitcoin Core integration

- [ ] Interact with Bitcoin Core using RPC or `bitcoin-cli` only inside the service.
- [ ] Keep RPC bound to localhost.
- [ ] Use wallet-specific RPC calls.
- [ ] Unlock wallet for minimum required time.
- [ ] Call `walletlock` immediately after spend attempt.
- [ ] Never implement endpoints for `dumpprivkey`, `dumpwallet`, `sendall`, arbitrary RPC, or arbitrary shell.
- [ ] Log txid and safe metadata only.

### 5. Ledger integration

- [ ] Require ledger pre-write verification before spend.
- [ ] Record spend result after broadcast.
- [ ] Record rejected attempts.
- [ ] Record service errors.
- [ ] Expose safe daily spend totals.

### 6. Tests

- [ ] Unit-test limit enforcement with fake Bitcoin Core backend.
- [ ] Integration-test with regtest if available.
- [ ] Test over-limit spend rejection.
- [ ] Test prohibited category rejection.
- [ ] Test missing policy/budget/ledger references rejection.
- [ ] Test duplicate idempotency behavior.
- [ ] Test wallet lock is attempted after spend.
- [ ] Test passphrase is never logged.

### 7. Acceptance criteria

- [ ] No direct wallet access from OpenClaw.
- [ ] Every spend is capped and auditable.
- [ ] Service fails closed on config, ledger, or Bitcoin Core errors.
