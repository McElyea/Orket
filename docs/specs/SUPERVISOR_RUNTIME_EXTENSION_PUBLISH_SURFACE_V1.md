# Supervisor Runtime Extension Publish Surface V1

Last updated: 2026-04-01
Status: Active
Owner: Orket Core
Related authority:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
3. `docs/guides/external-extension-authoring.md`
4. `docs/templates/external_extension/README.md`
5. `CURRENT_AUTHORITY.md`

## Authority posture

This document is the active durable contract authority for the Packet 1 external-extension publish surface.

It defines one authoritative published artifact family, one version-and-tag authority rule, one maintainer publish path, and one operator intake path back to strict host validation.
It does not authorize registry, marketplace, catalog, cloud distribution, or runtime-authority expansion.

## Purpose

Define one publish story for the already-fixed Packet 1 external-extension package surface so maintainers and operators can move one truthful artifact from source tree to host validation without creating a second authority center.

## Scope

In scope:
1. one authoritative published artifact family built from the canonical external extension repository shape
2. one version authority rule spanning `pyproject.toml`, manifest `extension_version`, and release tag
3. one canonical maintainer path for build and release verification
4. one canonical tagged automation path
5. one operator intake path from the published artifact back to `orket ext validate <extension_root> --strict --json`

Out of scope:
1. package-surface redesign
2. manifest-family redesign
3. registry, marketplace, or discovery product work
4. install-time auto-discovery or runtime authority changes
5. API or UI wrappers for publish flows

## Decision lock

The following remain fixed for Packet 1:
1. the authoritative published artifact family is one source distribution: `dist/<normalized_project_name>-<project.version>.tar.gz`
2. `project.version` in `pyproject.toml` must equal manifest `extension_version`
3. the canonical release tag is `v<project.version>`
4. the canonical host-validation path remains `orket ext validate <extension_root> --strict --json`
5. the authoritative source distribution must preserve one root-level manifest plus `src/`, `tests/`, and `scripts/`
6. publish success remains subordinate to host validation and does not grant runtime authority
7. tagged publish automation may preserve the source distribution artifact, but that automation is not a second authority source

## Canonical published artifact

Packet 1 publishes one authoritative artifact family only:
1. source distribution (`sdist`)

The authoritative source distribution must:
1. be built from the canonical external extension repository root
2. preserve the root manifest
3. preserve `pyproject.toml`
4. preserve `src/`
5. preserve `tests/`
6. preserve `scripts/`

Derivative artifacts may exist outside this contract, but Packet 1 does not treat them as operator-authoritative intake surfaces.

## Canonical maintainer path

The canonical maintainer path from the extension repository root is:
1. `./scripts/build-release.sh`
2. `./scripts/build-release.ps1`
3. `./scripts/verify-release.sh v<extension_version>`
4. `./scripts/verify-release.ps1 v<extension_version>`

The canonical tagged automation path is:
1. `.gitea/workflows/release.yml`

That path must:
1. validate and test the source repository
2. build the authoritative source distribution
3. fail closed on tag/version drift
4. preserve the source distribution as the tagged release artifact

## Canonical operator intake path

The canonical operator intake path from a published extension artifact is:
1. retrieve the tagged source distribution artifact
2. extract the `.tar.gz` into a local staging directory
3. run `orket ext validate <extracted_root> --strict --json`
4. interpret success as admissible for execution consideration only
5. interpret failure as fail-closed non-admission

Packet 1 does not treat source distribution retrieval or extraction as runtime authority.

## Fail-closed publish rules

Packet 1 must fail closed on:
1. version drift between `pyproject.toml` and manifest `extension_version`
2. release tag drift from `v<project.version>`
3. missing authoritative source distribution
4. source distribution filename or root-directory drift from the normalized project name plus version
5. source distribution layout drift that drops the root manifest, `src/`, `tests/`, or `scripts/`
6. any wording or tooling that implies publish success grants runtime authority

## Canonical proof entrypoints

1. `python -m pytest -q tests/interfaces/test_ext_init_cli.py tests/interfaces/test_ext_validate_cli.py tests/application/test_check_extension_release_script.py`
2. `python -m pytest -q docs/templates/external_extension/tests/test_manifest_validation.py`
3. `./scripts/build-release.sh` from the template or a copied external extension repository
4. `./scripts/verify-release.sh v<extension_version>` from the template or a copied external extension repository
5. tagged `.gitea/workflows/release.yml` proof that extracts the published source distribution and re-runs strict host validation

## Contract maintenance rules

If this contract changes materially, the same change must update:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md` when the source package shape changes
3. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md` when the validation relationship changes
4. `docs/guides/external-extension-authoring.md`
5. `docs/templates/external_extension/README.md`
6. `docs/templates/external_extension/.gitea/workflows/ci.yml`
7. `docs/templates/external_extension/.gitea/workflows/release.yml`
8. `CURRENT_AUTHORITY.md`
