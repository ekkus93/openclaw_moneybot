# `metrics_export_plugin`

## Goal

Produce bounded local exports for review, payout, and strategy metrics without exposing raw SQL or unrestricted filesystem access.

## Authority boundaries

- Supports only approved export shapes.
- Writes outputs only under the configured export root.
- Archives generated outputs and summaries through the evidence archiver.
- Does not expose arbitrary queries, secrets, or full unbounded ledger dumps.

## Inputs/outputs

- **Input:** `MetricsExportRequest`
- **Output:** `MetricsExportResult`
- Supported export types:
  - `experiment_reviews`
  - `payout_reconciliations`
  - `strategy_summaries`

## Config

- `enabled`
- `export_root`
- `max_rows`

## Failure modes

- Rejects unsupported export types and formats.
- Rejects unsupported outcome filters.
- Bounds oversized exports to the configured row cap.
- Rejects output paths that would escape the export root.

## Tests

- Stable approved export output
- Unsupported filter rejection
- Sensitive-field exclusion
- Safe bounding of oversized requests
- Export evidence and audit linkage

## Acceptance criteria

- Review and strategy flows can consume deterministic historical summaries safely.
- Export behavior remains bounded, typed, and auditable.
