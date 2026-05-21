# rules_snapshot_gateway

## Goal

Capture, normalize, hash, and diff allowlisted rule snapshots so stale approvals are detectable and auditable.

## Authority boundaries

- Read-only snapshot capture from allowlisted hosts.
- No unrestricted browsing or JavaScript execution.
- Rejects unsupported hosts, content types, and oversized content.

## Inputs and outputs

- Capture requests include opportunity ID, source URL, content text, and content type.
- Results include raw and normalized hashes, freshness, diff output, evidence IDs, and ledger linkage.

## Config

- `enabled`
- `allowed_hosts`
- `allowed_content_types`
- `max_content_bytes`
- `stale_after_hours`

## Failure modes

- Non-allowlisted hosts, unsupported content types, and oversized payloads are rejected and audited.

## Tests

- Initial capture, same-content recapture, meaningful diffs, unsafe content rejection, and evidence/ledger linkage.

## Acceptance criteria

- Terms review can rely on versioned, archived, auditable snapshots.
