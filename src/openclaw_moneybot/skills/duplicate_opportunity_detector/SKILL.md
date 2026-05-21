# duplicate_opportunity_detector

## Purpose

Prevent duplicate work across reposted or substantially identical opportunities.

## Inputs

- candidate opportunity fingerprint
- prior opportunity fingerprints

## Outputs

- duplicate flag
- confidence and match reasons
- safe next steps

## Fail-closed behavior

- strong duplicate evidence blocks normal continuation
- incomplete metadata degrades to review, not false uniqueness

## Non-goals

- fuzzy semantic search outside local opportunity history
