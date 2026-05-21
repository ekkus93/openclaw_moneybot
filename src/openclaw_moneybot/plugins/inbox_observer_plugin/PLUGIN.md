# inbox_observer_plugin

## Goal

Provide a bounded read-only inbox observation layer for payout and follow-up state.

## Authority boundaries

- Observes only the configured bot mailbox.
- Never sends or auto-replies.
- Archives safe message excerpts and attachment metadata only.

## Inputs and outputs

- Batch observation requests accept inbound message metadata, bodies, and attachment metadata.
- Results include deterministic classifications, thread linkage, attachment actions, evidence IDs, and ledger linkage.

## Config

- `enabled`
- `mailbox_address`
- `allowed_attachment_extensions`
- `max_body_excerpt_chars`
- `max_attachment_bytes`

## Failure modes

- Non-allowlisted mailbox access is rejected and audited.
- Unsupported or oversized attachments are quarantined or rejected safely.

## Tests

- Payout, opt-out, complaint, and unknown classifications, mailbox validation, attachment safety, and thread linkage.

## Acceptance criteria

- Follow-up and reconciliation flows can consume inbound state without adding any send capability.
