# Supervisor Runtime Extension Package Surface V1

Last updated: 2026-04-01
Status: Active
Owner: Orket Core
Related authority:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md`
3. `docs/guides/external-extension-authoring.md`
4. `docs/templates/external_extension/README.md`
5. `CURRENT_AUTHORITY.md`

## Authority posture

This document is the active durable contract authority for the current Packet 1 external-extension package surface.

It defines one canonical external package shape, one canonical bootstrap expectation, one canonical author path, and one canonical operator validation path.
It is the source-surface authority that the publish contract builds from.
Publish behavior itself is governed separately by `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md`.

## Purpose

Define one external extension package story that is installable, host-validated, usable without repo-internal imports, and subordinate to host runtime authority.

## Scope

In scope:
1. one external extension repository rooted at `pyproject.toml` plus `extension.yaml` or `extension.yml` or `extension.json`
2. one canonical source-tree shape rooted under `src/`
3. one canonical test-tree shape rooted under `tests/`
4. one canonical bootstrap contract for SDK and host availability before validation
5. one canonical author path for strict validation, import scanning, and tests
6. one canonical operator path for strict host validation
7. one explicit relationship between package metadata and manifest metadata

Out of scope:
1. publish or distribution hardening
2. registry, marketplace, wheelhouse, or catalog design
3. new manifest families beyond `manifest_version: v0`
4. runtime authority changes derived from package validation
5. API or UI wrappers around package validation

## Decision lock

The following remain fixed for Packet 1:
1. `manifest_version: v0` is the only admitted manifest family
2. the host validation path remains `orket ext validate <extension_root> --strict --json`
3. validation success remains admissibility evidence only and does not grant runtime authority
4. capability enforcement, namespace enforcement, and execution truth remain host-owned
5. external extension code must not import internal `orket.*` modules
6. publish behavior is governed separately by `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md` and does not alter the package-shape contract

## Canonical repository shape

The supported Packet 1 external extension repository contains:
1. `pyproject.toml`
2. one manifest at the repository root:
   1. `extension.yaml`, or
   2. `extension.yml`, or
   3. `extension.json`
3. `src/<extension_pkg>/`
4. `tests/`
5. `scripts/`

The canonical checked-in reference is `docs/templates/external_extension/`.

## Package and manifest relationship

The package surface keeps these relationships explicit:
1. `project.version` in `pyproject.toml` must equal manifest `extension_version`
2. `extension_id` remains manifest authority and is not derived from `project.name`
3. workload entrypoints must resolve to Python modules under the extension source tree
4. when `src/` exists, host import scanning and SDK import scanning are scoped to that source tree rather than unrelated local environment folders

## Canonical bootstrap contract

The external author bootstrap contract is:
1. Python 3.11 or newer is available
2. one SDK install spec is supplied through `ORKET_SDK_INSTALL_SPEC`
3. the Orket host CLI is already available as `orket`, or one host install spec is supplied through `ORKET_HOST_INSTALL_SPEC`
4. the canonical template bootstrap wrappers are:
   1. `./scripts/install.sh`
   2. `./scripts/install.ps1`

The SDK install spec may be a local wheel path or another explicit pip install spec supplied by Orket Core.
SDK distribution authority remains separate from this extension package and publish surface.

## Canonical author path

After bootstrap, the canonical author validation path from the extension root is:
1. `python -m orket_extension_sdk.validate . --strict --json`
2. `python -m orket_extension_sdk.import_scan src --json`
3. `orket ext validate . --strict --json`
4. `python -m pytest -q tests/`

The canonical wrapper scripts for that path are:
1. `./scripts/validate.sh`
2. `./scripts/validate.ps1`

## Canonical operator path

The canonical operator path for a local external extension is:
1. point the host at the extension root
2. run `orket ext validate <extension_root> --strict --json`
3. interpret success as admissible for execution consideration only
4. interpret failure as fail-closed non-admission

## Fail-closed compatibility rules

Packet 1 must fail closed on:
1. unsupported manifest family
2. missing manifest
3. invalid or missing entrypoint
4. disallowed internal `orket.*` imports
5. unknown capabilities under strict validation

## Canonical proof entrypoints

1. `python -m pytest -q tests/interfaces/test_ext_validate_cli.py`
2. `python -m pytest -q tests/sdk/test_validate_module.py tests/sdk/test_manifest.py tests/sdk/test_import_scan_module.py`
3. `python -m build --sdist --wheel ./orket_extension_sdk`
4. clean-environment wheel install smoke for `orket_extension_sdk`
5. clean-environment template bootstrap plus strict author-path proof from `docs/templates/external_extension/`

## Contract maintenance rules

If this contract changes materially, the same change must update:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md` when the validation seam changes
3. `docs/guides/external-extension-authoring.md`
4. `docs/templates/external_extension/README.md`
5. `docs/templates/external_extension/.gitea/workflows/ci.yml`
6. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md` when the publish relationship changes
7. `CURRENT_AUTHORITY.md`
