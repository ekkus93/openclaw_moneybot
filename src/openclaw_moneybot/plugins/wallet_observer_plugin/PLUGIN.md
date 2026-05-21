# wallet_observer_plugin

## Goal

Provide a read-only wallet observation layer for reconciliation and payout tracking.

## Authority boundaries

- No unlock, send, broadcast, or raw spend capability.
- Reads balance and tracked transaction metadata only.
- Audits observation failures explicitly.

## Inputs and outputs

- Balance observation requests return deterministic wallet balance snapshots.
- Transaction observation requests return confirmation state, observed satoshis/fees, mismatch fields, evidence IDs, and ledger linkage.

## Config

- `enabled`
- `allowed_assets`
- `read_only`

## Failure modes

- Unsupported assets are rejected.
- Backend failures generate audit records and safe structured results.

## Tests

- Balance reads, tx lookup, missing txid behavior, mismatch surfacing, audit events, and read-only boundary checks.

## Acceptance criteria

- Reconciliation can inspect wallet state without any spend authority.
