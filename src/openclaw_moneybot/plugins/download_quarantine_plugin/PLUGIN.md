# download_quarantine_plugin

## Goal

Stage untrusted downloads and attachments in a bounded quarantine pipeline before promotion into trusted evidence.

## Authority boundaries

- Never executes, opens, or extracts content outside the quarantine root.
- Enforces host, extension, MIME, size, and archive-safety checks.
- Promotes only staged files into the evidence archive.

## Inputs and outputs

- Ingest requests stage one file plus safe metadata.
- Promotion requests archive a staged file and record provenance-preserving promotion metadata.

## Config

- `enabled`
- `quarantine_root`
- `allowed_hosts`
- `allowed_extensions`
- `allowed_mime_types`
- `max_file_bytes`
- `max_archive_entries`
- `max_nested_bytes`

## Failure modes

- Path traversal, executable content, oversized files, non-allowlisted hosts, and unsafe archives are rejected.

## Tests

- Safe ingestion, executable rejection, oversized rejection, path traversal rejection, zip-bomb rejection, and promotion provenance checks.

## Acceptance criteria

- Downloads and attachments stay untrusted until deterministic validation and explicit promotion succeed.
