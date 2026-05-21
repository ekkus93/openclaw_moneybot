# revenue_reconciler

## Purpose

Compare expected payouts against actual receipts, confirmations, and proof so MoneyBot can track revenue accurately.

## Inputs

- expected payout amount and timing
- observed payout evidence
- counterparty and reference metadata

## Outputs

- structured reconciliation status
- variance and reason codes
- follow-up recommendation flag
- archived reconciliation snapshot

## Fail-closed behavior

- ambiguous multiple matches become review-required
- missing payout proof remains unresolved

## Example

If the plan expected `$25` and only `$10` arrives after the expected payout window, the skill returns `underpaid` or `late` and recommends follow-up.

## Non-goals

- sending follow-up messages
- over-matching unrelated receipts
