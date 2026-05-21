# `counterparty_snapshot_plugin`

## Goal

Capture low-risk public counterparty snapshots so downstream risk analysis can rely on archived evidence instead of ad hoc browsing.

## Authority boundaries

- Captures only operator-provided public page content from allowlisted hosts.
- Rejects private/login-like paths, non-allowlisted content types, oversized content, and sources marked as disallowed.
- Archives evidence and writes ledger/audit records, but does not log in, browse interactively, or assert unverifiable claims.

## Inputs/outputs

- **Input:** `CounterpartySnapshotRequest`
- **Output:** `CounterpartySnapshotResult`
- Extracts stable indicators like display name, support email, payout-terms presence, payment-proof presence, dispute-policy presence, and freshness metadata.

## Config

- `enabled`
- `allowed_hosts`
- `allowed_content_types`
- `max_content_bytes`
- `freshness_days`

## Failure modes

- Rejects unsupported source categories.
- Rejects non-allowlisted hosts or content types.
- Rejects oversized content and private/login-like URLs.
- Rejects sources explicitly marked as disallowed in the supplied content snapshot.

## Tests

- Supported public snapshot capture
- Allowlist rejection
- Incomplete-field handling
- Freshness preservation
- Deterministic repeated-capture comparison

## Acceptance criteria

- Counterparty-risk analysis can consume archived public evidence.
- The plugin remains bounded to low-risk public-data collection.
