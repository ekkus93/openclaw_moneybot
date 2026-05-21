# terms_change_monitor

## Purpose

Detect meaningful changes in opportunity rules or payout terms and prevent stale approvals from being reused blindly.

## Inputs

- prior rules snapshot
- current rules snapshot
- optional prior budget and TOS references

## Outputs

- typed change severity and changed fields
- recheck hooks for budget and policy
- archived diff snapshot
- durable ledger linkage

## Fail-closed behavior

- missing prior snapshots trigger conservative rechecks
- newly prohibited automation becomes `block` severity

## Example

If a platform newly adds “no bots” or cuts payout from `$25` to `$5`, the skill flags the change and forces refreshed downstream checks.

## Non-goals

- fetching arbitrary remote pages
- silently ignoring stale terms
