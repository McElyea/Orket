# Contract Delta: Supervisor Runtime Extension Publish Surface Hardening

Last updated: 2026-04-01
Status: Active historical delta
Owner: Orket Core

## Trigger

The active `Extension Publish Surface Hardening` lane converted the previously deferred publish story into one durable Packet 1 contract.

## Previous contract

Before this delta:
1. the active durable extension authority covered package surface and validation only
2. publish behavior was deferred or implied rather than specified
3. the current template build artifacts did not preserve the manifest-backed extension-root validation surface truthfully

## New contract

After this delta:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md` is the durable publish authority
2. Packet 1 admits one authoritative published artifact family only: source distribution (`sdist`)
3. the canonical release tag is `v<extension_version>`
4. the authoritative source distribution must preserve the root manifest plus `src/`, `tests/`, and `scripts/`
5. the canonical maintainer path is `build-release` plus `verify-release`
6. the canonical operator intake path from a published artifact is extract -> `orket ext validate <extracted_root> --strict --json`
7. publish success remains subordinate to host validation and host runtime authority

## Same-change authority sync

The same change must keep these surfaces aligned:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md`
3. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
4. `docs/guides/external-extension-authoring.md`
5. `docs/templates/external_extension/README.md`
6. `docs/templates/external_extension/.gitea/workflows/ci.yml`
7. `docs/templates/external_extension/.gitea/workflows/release.yml`
8. `CURRENT_AUTHORITY.md`

## Deferred explicitly

This delta does not authorize:
1. registry or marketplace product work
2. cloud distribution platform work
3. new manifest families
4. runtime auto-discovery or runtime authority expansion
