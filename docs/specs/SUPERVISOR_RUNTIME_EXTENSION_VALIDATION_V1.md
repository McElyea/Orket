# Supervisor Runtime Extension Validation V1

Last updated: 2026-03-31
Status: Active
Owner: Orket Core
Source requirements: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`
Implementation closeout authority: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/guides/external-extension-authoring.md`
2. `CURRENT_AUTHORITY.md`

## Authority posture

This document is the active durable contract authority for the completed Packet 1 extension manifest and host-side validation slice.

It standardizes one manifest family and one host-side validation path for Packet 1.
It does not authorize marketplace, cloud distribution, install-source plurality, or broader package-management behavior.

## Purpose

Define one host-owned extension validation contract so installable extension metadata remains explicit, fail-closed, and subordinate to host authority.

## Scope

In scope:
1. one SDK-first manifest family rooted at `extension.yaml`, `extension.yml`, or `extension.json`
2. one canonical validation path: `orket ext validate <extension_root> --strict --json`
3. one operator-visible diagnostic path: the fail-closed JSON result from that validation command
4. one unsupported-host-version rule: `manifest_version` must be `v0`

Out of scope:
1. marketplace or cloud distribution flows
2. multiple manifest contract families in parallel
3. broad install and update workflow standardization
4. any rule that grants runtime authority merely because validation passed

## Decision lock

The following remain fixed for Packet 1:
1. the host remains authoritative for policy enforcement, capability checks, namespace enforcement, execution truth, and auditability
2. the selected manifest family is the current SDK-first `manifest_version: v0` contract family
3. the selected validation path is `orket ext validate <extension_root> --strict --json`
4. unsupported manifest families fail closed before installable execution authority is considered
5. validation success does not create a second hidden runtime authority center

## Canonical manifest shape

The admitted Packet 1 manifest surface is:
1. `extension.yaml`, `extension.yml`, or `extension.json` at the extension root
2. required Packet 1 top-level fields:
   1. `manifest_version`
   2. `extension_id`
   3. `extension_version`
   4. `workloads`
3. required Packet 1 workload fields:
   1. `workload_id`
   2. `entrypoint`
   3. `required_capabilities`

For Packet 1, `required_capabilities` is the admitted capability-declaration surface for the selected host validation path.

## Validation path contract

The canonical Packet 1 operator validation path is:
1. `orket ext validate <extension_root> --strict --json`

That path must:
1. parse the admitted manifest family
2. validate workload entrypoint shape and importability
3. validate required capability declarations under strict mode
4. emit a machine-readable JSON result
5. fail closed on invalid manifest, unsupported host contract family, or disallowed internal import behavior

Non-strict validation may remain available for author ergonomics, but it is not the canonical Packet 1 host-admission path.

## Diagnostic contract

The canonical operator-visible diagnostic path is the fail-closed JSON result emitted by the host-side validation command.

At minimum, that diagnostic path must remain machine-readable enough to distinguish:
1. overall pass or fail
2. error count
3. warning count
4. stable error or warning codes
5. import-isolation scan results when host-side external validation includes them

Packet 1 does not require a separate UI or API wrapper around that JSON diagnostic surface.

## Unsupported-host-version rule

For Packet 1:
1. `manifest_version: v0` is the only admitted manifest contract family
2. any other manifest contract family is unsupported
3. unsupported contract families must fail closed at the host validation boundary before installable execution authority is considered

## Host-owned authority rule

Validation success does not grant runtime authority.

For Packet 1, the host remains authoritative for:
1. policy enforcement
2. capability checks
3. namespace enforcement
4. execution truth
5. auditability

Packet 1 does not treat validation, installability, or discoverability as permission to bypass host-owned runtime governance.

## Canonical seams and proof entrypoints

Current Packet 1 seam:
1. `orket ext validate <extension_root> --strict --json`

Current proof entrypoints:
1. `python -m pytest -q tests/interfaces/test_ext_validate_cli.py`
2. `python -m pytest -q tests/sdk/test_validate_module.py`

## Contract maintenance rules

If this contract changes materially, the same change must update:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
2. `docs/guides/external-extension-authoring.md` when the manifest or validation flow changes
3. `CURRENT_AUTHORITY.md` when the active spec set or extension validation authority story changes
4. `docs/API_FRONTEND_CONTRACT.md` when a future API surface exposes host-side extension validation or inspection behavior
