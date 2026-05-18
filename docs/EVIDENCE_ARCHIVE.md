# Evidence archive

The evidence archive stores immutable artifacts plus metadata JSON.

## Safety rules

- File-based archival is only allowed from configured `allowed_source_roots`.
- Sensitive paths such as `/etc`, `.ssh`, wallet files, browser cookie stores, and secret files are rejected.
- Directory inputs and oversized files are rejected.
- Archive filenames are generated internally.
- Optional text redaction removes obvious secrets from textual artifacts.

## Stored metadata

- related record type and ID
- evidence type
- source URL when available
- content SHA-256
- capture time
- redaction markers
