# account_eligibility_checker

## Purpose

Reject or flag opportunities that MoneyBot is not actually eligible to pursue before spending time or money.

## Inputs

- opportunity metadata
- rules text or archived evidence references
- bounded operator capability/profile data
- optional policy and TOS references

## Outputs

- typed eligibility decision
- blocked, missing, and review-required requirements
- safe next steps
- archived eligibility snapshot
- durable ledger linkage

## Fail-closed behavior

- missing rules become `incomplete`
- ambiguous requirements become `needs_review`
- incompatible requirements become `blocked`

## Example

If rules require a personal account, unsupported payout method, or blocked geography, the skill returns a non-eligible result and stops downstream planning.

## Non-goals

- creating accounts
- bypassing identity requirements
- inventing eligibility facts
