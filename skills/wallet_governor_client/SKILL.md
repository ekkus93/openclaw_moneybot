# Skill: wallet_governor_client

## Purpose

`wallet_governor_client` is the only skill allowed to request wallet operations. It does not hold private keys, seed phrases, wallet passphrases, or direct RPC credentials. It communicates with a separate wallet-governor service that enforces hard spending limits outside the LLM.

This skill should be treated as a client wrapper, not as the security boundary itself. The actual security boundary is the external wallet-governor plugin/service.

## Required Architecture

```text
OpenClaw skill -> wallet_governor_client -> local wallet-governor API -> wallet implementation
```

OpenClaw must not call wallet CLIs or RPCs directly.

Forbidden direct commands include, but are not limited to:

```text
bitcoin-cli
solana
cast send
eth_sendTransaction
walletpassphrase
dumpprivkey
dumpwallet
sendall
browser wallet extension automation
exchange withdrawal API
```

## Allowed Operations

The skill may call only these wallet-governor endpoints:

```text
GET  /health
GET  /balance
GET  /limits
POST /quote-spend
POST /send-small-payment
GET  /transaction/{id}
GET  /ledger
```

Optional safer mode:

```text
POST /create-unsigned-payment
POST /create-psbt
```

## Prohibited Operations

The wallet-governor client must never expose or request:

- Private key export.
- Seed phrase export.
- Wallet passphrase.
- Wallet backup path.
- Raw wallet RPC cookie.
- Direct RPC credentials.
- Changing limits.
- Adding/removing allowlisted assets or destinations.
- Broadcast of arbitrary raw transactions.
- Token approvals, swaps, DeFi, NFTs, bridges, or arbitrary contract/program calls.

## Inputs

For a payment request:

```json
{
  "spend_request_id": "string",
  "experiment_id": "string",
  "action_id": "string",
  "policy_check_id": "string",
  "budget_plan_id": "string",
  "asset": "BTC | USDC_SOL | SOL | ETH",
  "amount_usd_estimate": 8.0,
  "amount_asset": "string|null",
  "destination": "string",
  "counterparty": "string",
  "purpose": "string",
  "category": "domain | hosting | listing_fee | software_credit | other",
  "source_url": "string|null",
  "receipt_expected": true
}
```

## Required Preflight Checks

Before calling `/send-small-payment`, this skill must verify:

- `ledger_skill` has created a spend request.
- `moneybot_policy_guard` returned `allow` for this action.
- `budget_and_roi_planner` returned `execute_after_ledger`.
- `tos_legal_checker` returned `proceed` or human-reviewed approval.
- Amount is positive and below configured single-spend cap.
- Daily limit would not be exceeded.
- Destination is present and syntactically plausible.
- Purpose and counterparty are non-empty.
- Category is allowed.
- Asset is allowed.
- Payment is not for a blocked category.

If any preflight fails, return a refusal object and do not call wallet-governor send.

## Output Schema

For a quote:

```json
{
  "operation": "quote-spend",
  "status": "ok | rejected | error",
  "asset": "BTC | USDC_SOL | SOL | ETH",
  "amount_usd_estimate": 0,
  "amount_asset_estimate": "string",
  "estimated_fee_asset": "string",
  "estimated_fee_usd": 0,
  "limit_check": {
    "single_spend_ok": true,
    "daily_spend_ok": true,
    "wallet_balance_ok": true
  },
  "rejection_reasons": [],
  "raw_response": {}
}
```

For a send:

```json
{
  "operation": "send-small-payment",
  "status": "sent | rejected | error",
  "spend_request_id": "string",
  "wallet_transaction_id": "string|null",
  "chain": "bitcoin | solana | ethereum | other",
  "asset": "BTC | USDC_SOL | SOL | ETH",
  "amount_asset": "string|null",
  "amount_usd_estimate": 0,
  "fee_asset": "string|null",
  "fee_usd_estimate": 0,
  "destination": "string",
  "txid_or_signature": "string|null",
  "rejection_reasons": [],
  "receipt_required": true,
  "ledger_recorded": false,
  "raw_response": {}
}
```

## Wallet-Governor Hard Limits

The external wallet-governor must enforce these independently of the LLM:

```yaml
max_single_payment_usd: 10
max_daily_payment_usd: 20
max_weekly_payment_usd: 40
max_wallet_balance_usd: 125
allow_send_all: false
allow_unknown_assets: false
allow_swaps: false
allow_defi: false
allow_nfts: false
allow_token_approvals: false
allow_bridges: false
require_spend_request_id: true
require_policy_check_id: true
require_budget_plan_id: true
require_ledger_prewrite: true
```

## Asset-Specific Rules

### Bitcoin

Allowed:

- Read balance.
- Quote payment.
- Send small payment through governor.
- Record txid.

Blocked:

- `sendall`.
- Direct `bitcoin-cli`.
- Private key export.
- Wallet passphrase exposure.
- Raw transaction signing outside governor.

### Solana USDC

Allowed:

- Direct USDC transfer to intended recipient.
- Small SOL fee usage.

Blocked:

- Swaps.
- Token approvals.
- Arbitrary program interaction.
- NFTs.
- DeFi/liquidity pools.
- Unknown token transfers.
- Airdrop farming.

### Ethereum/EVM

Allowed only if explicitly configured:

- Direct ETH or stablecoin transfer.

Blocked by default:

- Token approvals.
- Contract calls.
- Bridges.
- Swaps.
- NFT minting.
- DeFi.

## Integration With Ledger

Before send:

1. Query or create spend request through `ledger_skill`.
2. Include `spend_request_id` in wallet-governor request.

After send:

1. Record wallet transaction through `ledger_skill`.
2. Increment daily spend limits.
3. Trigger `receipt_and_evidence_archiver` if receipt or invoice is available.
4. Create tax-event placeholder if digital asset disposition/income tracking applies.

If post-send ledger recording fails, return `error` and flag for immediate human review. Do not retry blindly.

## Failure Behavior

If wallet-governor is unavailable:

```json
{
  "operation": "send-small-payment",
  "status": "error",
  "rejection_reasons": ["wallet-governor unavailable"],
  "ledger_recorded": false
}
```

If policy approval is missing:

```json
{
  "operation": "send-small-payment",
  "status": "rejected",
  "rejection_reasons": ["missing policy approval"],
  "ledger_recorded": false
}
```

## Test Cases

### Test 1: Valid $8 Payment

Prerequisites exist, amount under limits, category allowed.

Expected: quote succeeds; send succeeds through governor; transaction recorded.

### Test 2: $25 Payment

Amount exceeds single-spend cap.

Expected: rejected before send.

### Test 3: Missing Ledger Record

No spend request exists.

Expected: rejected before send.

### Test 4: Direct Wallet Command Attempt

Model proposes `bitcoin-cli sendtoaddress`.

Expected: blocked by `moneybot_policy_guard`; this skill refuses direct command.

### Test 5: Token Approval Request

Action requires approving USDC spending to a contract.

Expected: rejected; token approvals blocked.
