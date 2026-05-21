# counterparty_risk_profiler

## Purpose

Score counterparties and platforms using deterministic local signals before MoneyBot commits work or spend.

## Inputs

- payout-history signals
- dispute/support observations
- domain and rules clarity signals

## Outputs

- risk tier
- explainable score
- positive, negative, and unknown signals
- recommended action

## Fail-closed behavior

- unknowns never silently produce low risk
- suspicious payment/KYC signals drive review or block decisions

## Non-goals

- browsing arbitrary sources
- replacing legal review
