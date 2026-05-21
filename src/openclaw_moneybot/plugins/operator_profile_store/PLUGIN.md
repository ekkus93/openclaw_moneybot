# operator_profile_store

## Goal

Provide a narrow local store of explicitly configured operator capabilities for deterministic eligibility checks.

## Authority boundaries

- Stores only approved capability metadata.
- Does not store personal credentials, KYC documents, or secrets.
- Returns `unknown` or `redacted` instead of guessing or exposing sensitive fields.

## Inputs and outputs

- Write requests accept a bounded set of operator-profile fields plus provenance metadata.
- Read requests return per-field availability, provenance, timestamps, and a safe redacted export.

## Config

- `enabled`
- `profile_path`
- `max_export_fields`

## Failure modes

- Unsupported or sensitive field writes are rejected.
- Malformed on-disk state fails closed.

## Tests

- Configured reads, unknown-field access, unsupported writes, sensitive-field rejection, provenance preservation, and version/audit linkage.

## Acceptance criteria

- Eligibility checks can consume deterministic operator facts without exposing secrets or personal-account credentials.
