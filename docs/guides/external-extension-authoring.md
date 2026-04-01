# External Extension Authoring Guide

Last updated: 2026-04-01
Status: Active
Owner: Orket Core

## Purpose

Define the canonical Packet 1 author path for external Orket extension repositories.

## Prerequisites

1. Python 3.11 or newer
2. One SDK install spec supplied through `ORKET_SDK_INSTALL_SPEC`
3. `orket` CLI available for host-side validation, or one host install spec supplied through `ORKET_HOST_INSTALL_SPEC`

## Canonical Starter Template

Use:
`docs/templates/external_extension/`

This template provides:
1. manifest and package metadata
2. `src/` extension module layout
3. install, validate, build-release, and verify-release scripts (Windows and Unix)
4. CI template in `.gitea/workflows/ci.yml`
5. tag-release workflow in `.gitea/workflows/release.yml`

## Canonical Package Surface

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

The canonical metadata relationship is:
1. `project.version` in `pyproject.toml` must match manifest `extension_version`
2. `extension_id` remains manifest authority and is not derived from `project.name`
3. workload entrypoints must resolve under the extension source tree

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

## Canonical Bootstrap

Activate the Python environment you want the extension to use before running bootstrap scripts.

Set these before bootstrap:
1. `ORKET_SDK_INSTALL_SPEC`
   - one pip install spec for `orket-extension-sdk`
   - this may be a local wheel path or another explicit install spec supplied by Orket Core
   - SDK distribution authority remains separate from this extension publish surface
2. `ORKET_HOST_INSTALL_SPEC`
   - optional if `orket` is already available
   - otherwise one pip install spec that makes the `orket` CLI available

Canonical bootstrap wrappers:
1. Unix: `./scripts/install.sh`
2. PowerShell: `./scripts/install.ps1`

Those scripts:
1. install the SDK from `ORKET_SDK_INSTALL_SPEC`
2. install the host CLI from `ORKET_HOST_INSTALL_SPEC` when `orket` is not already present
3. install the extension package editable with its dev extras without assuming package-index publish
4. write into the currently active Python environment

## Canonical Author Loop

Run these from the extension repository root:

1. `python -m orket_extension_sdk.validate . --strict --json`
2. `python -m orket_extension_sdk.import_scan src --json`
3. `orket ext validate . --strict --json`
4. `python -m pytest -q tests/`

Canonical wrapper scripts:
1. Unix: `./scripts/validate.sh`
2. PowerShell: `./scripts/validate.ps1`

Host validation interpretation:
1. `manifest_version` other than `v0` must fail closed with `E_SDK_MANIFEST_VERSION_UNSUPPORTED`.
2. `--strict` promotes unknown capability declarations from warnings to errors.
3. `orket ext validate` scans extension Python source, using `src/` when present instead of unrelated local virtualenv trees.

## Canonical Publish Path

Run these from the extension repository root:

1. `./scripts/build-release.sh`
2. `./scripts/build-release.ps1`
3. `./scripts/verify-release.sh v<extension_version>`
4. `./scripts/verify-release.ps1 v<extension_version>`

Canonical publish rules:
1. the authoritative published artifact family is one source distribution: `dist/<normalized_project_name>-<version>.tar.gz`
2. `project.version` in `pyproject.toml` must match manifest `extension_version`
3. the canonical release tag is `v<extension_version>`
4. the source distribution must preserve the root manifest plus `src/`, `tests/`, and `scripts/`
5. publish success does not grant runtime authority

The canonical tagged automation path is:
1. `.gitea/workflows/release.yml`

That workflow must:
1. validate and test the source repository
2. build the authoritative source distribution
3. fail closed on tag/version drift
4. prove operator intake by extracting the published artifact and re-running strict host validation
5. preserve the source distribution as the tagged release artifact

## Canonical Operator Path

The minimum operator flow for a local external extension is:
1. point the host at the extension root
2. run `orket ext validate <extension_root> --strict --json`
3. treat success as admissible for execution consideration only
4. treat failure as fail-closed non-admission

The canonical operator flow from a published artifact is:
1. retrieve the tagged source distribution artifact produced by `.gitea/workflows/release.yml`
2. extract the `.tar.gz` into a local staging directory
3. run `orket ext validate <extracted_root> --strict --json`
4. treat success as admissible for execution consideration only
5. treat failure as fail-closed non-admission

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

## CI and Release Baseline

Use the template workflow at:
`docs/templates/external_extension/.gitea/workflows/ci.yml`

The baseline sequence is:
1. provide `ORKET_SDK_INSTALL_SPEC`
2. provide `ORKET_HOST_INSTALL_SPEC` unless `orket` is already on the runner path
3. run the canonical install wrapper
4. run strict SDK validation
5. run strict import scan
6. run strict host validation
7. run tests
8. build the authoritative source distribution
9. verify the authoritative source distribution without a tag requirement

Use the tag workflow at:
`docs/templates/external_extension/.gitea/workflows/release.yml`

The tagged release sequence is:
1. run the CI-proofed source validations
2. build the authoritative source distribution
3. verify `v<extension_version>` tag alignment
4. prove operator intake from the published source distribution
5. upload `dist/*.tar.gz` as the canonical tagged release artifact
