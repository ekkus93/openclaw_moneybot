# opportunity_index_plugin

## Goal

Provide a bounded local index for duplicate checks and historical opportunity lookup.

## Authority boundaries

- Reads from approved ledger APIs only.
- No arbitrary SQL surface.
- Rebuilds and queries are deterministic and bounded.

## Inputs and outputs

- Rebuild/update flows produce local index entries plus ledger linkage.
- Similarity queries return bounded matches with deterministic explanations.

## Config

- `enabled`
- `index_path`
- `max_results`

## Failure modes

- Unknown opportunities and oversized query shapes are rejected.
- Malformed on-disk index state fails closed.

## Tests

- Duplicate surfacing, non-overmerge behavior, incremental updates, unsafe query rejection, and deterministic rebuilds.

## Acceptance criteria

- Duplicate detection and strategy-memory flows have a fast local index without exposing raw database access.
