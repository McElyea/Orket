# OS Versioning Policy

Last updated: 2026-02-22
Status: Normative

## Scope
Applies to all files listed in `docs/projects/OS/contract-index.md`.

## Rules
1. Major version change (`vN -> vN+1`) is required for breaking shape changes.
2. Minor version changes are additive only:
new optional fields, new optional enum values, new non-breaking docs.
3. Patch updates may clarify wording without changing meaning.
4. Contract schemas MUST declare:
`version` as a required field and `additionalProperties: false`.

## Compatibility Window
1. One prior major version may be accepted during migration.
2. Current major version is authoritative in CI.
3. Deprecation notice must be documented before removal.

## Deprecation Timeline
1. Mark deprecated in docs with replacement.
2. Keep compatibility for at least one full release window.
3. Remove only after CI and migration map are updated.

## CI Requirements
1. Schema validation runs on all contract fixtures.
2. Version mismatch fails CI.
3. Breaking shape change without major bump fails CI.
