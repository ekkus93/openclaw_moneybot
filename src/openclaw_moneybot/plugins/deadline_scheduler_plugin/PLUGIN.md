# deadline_scheduler_plugin

## Goal

Track deadlines, cooldowns, and retry windows in a deterministic local planner.

## Authority boundaries

- Stores schedule state only.
- Never sends notifications or emails.
- Marks ambiguous or conflicting dates explicitly instead of guessing.

## Inputs and outputs

- Schedule requests store one deadline item plus provenance and evidence references.
- Summary queries return overdue, upcoming, uncertain, conflicting, and cooling-down reference IDs.

## Config

- `enabled`
- `schedule_path`
- `default_timezone`
- `max_items`

## Failure modes

- Missing or malformed schedule state fails closed.
- Ambiguous text becomes `uncertain`.
- Conflicts generate audit records.

## Tests

- Explicit parsing, ambiguous dates, overdue detection, cooldown tracking, and conflict surfacing.

## Acceptance criteria

- Queue and follow-up logic can consume deterministic schedule state without false certainty.
