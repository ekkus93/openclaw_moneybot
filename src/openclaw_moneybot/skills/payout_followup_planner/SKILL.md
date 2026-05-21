# payout_followup_planner

## Purpose

Recommend safe follow-up actions when a payout is late, missing, partial, or disputed.

## Inputs

- reconciliation status
- evidence availability
- counterparty risk

## Outputs

- bounded recommendation
- whether a draft is needed
- timing guidance and stop conditions

## Fail-closed behavior

- high-risk or ambiguous cases require manual review
- the skill never auto-sends outreach

## Non-goals

- escalation beyond safe, documented recommendations
