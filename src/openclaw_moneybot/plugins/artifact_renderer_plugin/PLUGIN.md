# artifact_renderer_plugin

## Goal

Deterministically assemble local submission and proof artifacts from approved templates and evidence references.

## Authority boundaries

- Uses only local templates under an approved template root.
- Never submits, sends, or fetches remote templates.
- Rejects out-of-bounds output paths and unknown evidence references.

## Inputs and outputs

- Render requests include a template name, field values, and evidence references.
- Results include rendered paths, manifest path, checksums, evidence IDs, and ledger linkage.

## Config

- `enabled`
- `template_root`
- `render_root`
- `max_bundle_files`

## Failure modes

- Missing required fields, placeholder values, unknown templates, and out-of-bounds render paths are rejected.

## Tests

- Valid render output, missing-field rejection, template rejection, path safety, and deterministic manifest/checksum behavior.

## Acceptance criteria

- Submission packages are deterministic, reviewable, archived, and never auto-submitted.
