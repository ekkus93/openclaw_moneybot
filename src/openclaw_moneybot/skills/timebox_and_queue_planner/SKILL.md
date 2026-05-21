# timebox_and_queue_planner

## Purpose

Prioritize bounded experiments by ROI, deadline, uncertainty, and current capacity.

## Inputs

- candidate queue items
- budget headroom
- concurrency caps

## Outputs

- ordered queue items
- deterministic priorities
- defer reasons when applicable

## Fail-closed behavior

- review-blocked or over-budget items are deferred
- repeated losers are deprioritized

## Non-goals

- bypassing policy, budget, or review gates
