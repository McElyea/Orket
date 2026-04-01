# External Extension Authoring Guide

Last updated: 2026-03-31
Status: Active
Owner: Orket Core

## Purpose

Define the current bootstrap flow for SDK-first external extension repositories.

## Prerequisites

1. Python 3.11 or newer
2. `orket-extension-sdk` installed
3. `orket` CLI available for host-side validation (`orket ext validate`)

## Canonical Starter Template

Use:
`docs/templates/external_extension/`

This template provides:
1. manifest and package metadata
2. `src/` extension module layout
3. install, validate, and run scripts (Windows and Unix)
4. CI template in `.gitea/workflows/ci.yml`

## Migration Boundary

This guide currently defines the migration boundary and conformance entrypoints. It does not yet claim a complete migration-pack rollout.

Current boundary items:
1. reference extension target: `docs/templates/external_extension/`
2. canonical conformance entrypoints:
   1. `python -m orket_extension_sdk.validate . --strict --json`
   2. `orket ext validate . --strict --json`
3. migration comparison mode: before/after validation against the same repository root
4. deprecation/removal tracking stays explicit and table-driven until a follow-on migration lane ships the full pack

## Deprecation Tracking Skeleton

Use this table shape when a compatibility-only seam is scheduled for removal:

| Legacy Seam | Replacement | Admission Rule | Removal Gate | Status |
|---|---|---|---|---|
| `<legacy entrypoint>` | `<canonical extension seam>` | `<who may still use it and why>` | `<what must pass before removal>` | `planned` |

## Required Repository Layout

Minimum expected structure:

```text
extension.yaml
pyproject.toml
src/<extension_pkg>/
tests/
scripts/
```

For `src/` layouts, entrypoints in `extension.yaml` should use package-module notation:
`<extension_pkg>.<module>:<symbol>`

## Manifest and Capability Rules

1. `extension.yaml` is required at repository root.
2. `manifest_version: v0` is the only admitted Packet 1 manifest family.
3. Unsupported manifest families fail closed during host-side validation before extension execution authority is considered.
4. Every workload must declare:
   1. `workload_id`
   2. `entrypoint`
   3. `required_capabilities`
5. Unknown capabilities are warnings by default and errors under strict validation.
6. Runtime authority capabilities must be requested, not reimplemented in extension code.

## Validation Workflow

Run these from the extension repository root:

1. Manifest + entrypoint + capability validation:
   `python -m orket_extension_sdk.validate . --json`
2. Static import isolation scan:
   `python -m orket_extension_sdk.import_scan src --json`
3. Host-side external extension validation:
   `orket ext validate . --json`

Strict mode:

1. `python -m orket_extension_sdk.validate . --strict --json`
2. `orket ext validate . --strict --json`

Host validation interpretation:
1. `manifest_version` other than `v0` must fail closed with `E_SDK_MANIFEST_VERSION_UNSUPPORTED`.
2. `--strict` promotes unknown capability declarations from warnings to errors.

## Testing Guidance by Layer

1. `unit`: config parsing, helper functions, deterministic transforms
2. `contract`: manifest schema and capability declarations
3. `integration`: entrypoint importability and end-to-end validate commands

Prefer real validation commands over mocks when asserting extension readiness.

## Common Failure Codes

1. `E_SDK_MANIFEST_NOT_FOUND`: missing `extension.yaml`/`extension.yml`/`extension.json`
2. `E_SDK_ENTRYPOINT_INVALID`: malformed `<module>:<symbol>` entrypoint
3. `E_SDK_ENTRYPOINT_MISSING`: module file or exported symbol could not be resolved
4. `E_SDK_CAPABILITY_UNKNOWN`: required capability is outside current vocabulary
5. `E_SDK_IMPORT_FORBIDDEN`: extension source imports internal `orket.*` modules
6. `E_SDK_MANIFEST_VERSION_UNSUPPORTED`: manifest uses an unsupported contract family

## CI Baseline

Use the template workflow at:
`docs/templates/external_extension/.gitea/workflows/ci.yml`

The baseline sequence is:
1. install SDK and package deps
2. run SDK validation
3. run import scan
4. run tests
