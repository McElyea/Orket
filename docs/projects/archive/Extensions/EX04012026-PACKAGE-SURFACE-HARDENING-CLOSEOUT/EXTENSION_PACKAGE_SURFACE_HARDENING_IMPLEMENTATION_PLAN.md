# Extension Package Surface Hardening Implementation Plan

Last updated: 2026-04-01
Status: Archived
Owner: Orket Core

## Purpose

Turn the current Packet 1 extension surfaces into one canonical external-extension package story that is installable, host-validated, usable by extension authors without repo-internal knowledge, and subordinate to host runtime authority.

This lane hardens package surface only.
Publish stays out.

## Active authority inputs

1. `CURRENT_AUTHORITY.md`
2. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
3. `docs/guides/external-extension-authoring.md`
4. `docs/templates/external_extension/README.md`
5. `docs/templates/external_extension/.gitea/workflows/ci.yml`
6. `.gitea/workflows/sdk-package-release.yml`
7. `orket_extension_sdk/`
8. `tests/interfaces/test_ext_validate_cli.py`
9. `tests/sdk/test_validate_module.py`
10. `tests/sdk/test_manifest.py`
11. `tests/sdk/test_import_scan_module.py`

## Decision lock

The lane stays fixed to these points:
1. package only, not publish
2. no registry, marketplace, wheelhouse distribution, or public release-flow expansion
3. existing SDK release automation may be used as proof input, but publish is not the deliverable
4. Packet 1 manifest family stays fixed at `manifest_version: v0`
5. admitted manifest fields stay fixed to:
   1. `manifest_version`
   2. `extension_id`
   3. `extension_version`
   4. `workloads[*].workload_id`
   5. `workloads[*].entrypoint`
   6. `workloads[*].required_capabilities`
6. the canonical host-validation path stays fixed to `orket ext validate <extension_root> --strict --json`
7. validation success does not grant execution authority
8. capability enforcement, namespace enforcement, and execution truth remain host-owned
9. the supported author path stays repo-external through the template and current author guide
10. there is no supported "import private monorepo internals" escape hatch

## Scope

### 1. One canonical package surface

Define one supported external extension repo and package layout.

This lane must answer:
what exact thing is an extension author supposed to build?

Required outputs:
1. one expected root layout
2. one canonical `pyproject.toml` expectation
3. one canonical `extension.yaml` / `extension.yml` / `extension.json` expectation
4. one canonical source-tree expectation
5. one canonical test-tree expectation
6. one canonical install or bootstrap expectation
7. one canonical relationship between package metadata and manifest metadata

### 2. One canonical validation and capability story

Lock validation around the current real seams:
1. SDK-side manifest and entrypoint validation
2. SDK-side import-isolation scan
3. host-side strict validation through `orket ext validate <extension_root> --strict --json`
4. strict capability declaration checking through `required_capabilities`

This lane must answer:
what exactly must pass before an extension is considered host-admissible?

### 3. One operator path

Define the minimum operator-facing flow for a local external extension:
1. point the host at the extension root
2. run canonical strict validation
3. interpret machine-readable pass or fail output
4. understand that success means admissible for execution consideration, not runtime-authoritative

This lane must answer:
what is the operator supposed to run, and what does success actually mean?

### 4. One extension-author path

Define the minimum author loop:
1. create an extension from the supported template
2. run SDK validation
3. run import scan
4. run host validation
5. run tests

This lane must answer:
how does an author succeed without knowing repo internals?

### 5. One Packet 1 compatibility story

Lock the minimal compatibility story, including:
1. the current supported manifest family
2. SDK version authority
3. failure on unsupported manifest family
4. failure on disallowed internal imports
5. fail-closed strict capability validation expectations

This lane must answer:
what is supported now, and what fails closed now?

## Non-goals

This lane explicitly refuses:
1. publish or distribution hardening
2. package registry strategy
3. marketplace or external catalog or discovery flow
4. a product story for how users download extensions
5. a new manifest family
6. broader manifest schema redesign
7. new execution authority paths
8. new API or UI wrappers for extension validation
9. install-time auto-execution or discovery authority
10. runtime facade reduction hidden inside package work
11. repo modularization disguised as extension ergonomics
12. capability-model broadening beyond the current Packet 1 declaration and validation surface unless required in the same truthful change

## Same-change update targets

At minimum, lane execution must keep these surfaces aligned in the same change when their story changes:
1. `docs/ROADMAP.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
4. `docs/guides/external-extension-authoring.md`
5. `docs/templates/external_extension/README.md`
6. `docs/templates/external_extension/.gitea/workflows/ci.yml`
7. `.gitea/workflows/sdk-package-release.yml`

If the package surface becomes durable enough to stand alone, extract a separate canonical package-surface spec instead of overloading the validation spec.

## Proof gates

### Gate 1 - SDK package authority proof

Prove the SDK is a real installable package, not just an in-repo convenience surface.

Required proof:
1. build wheel and sdist for `orket_extension_sdk`
2. install the built wheel in a clean virtual environment
3. import succeeds without hidden dependence on the main `orket` package import path
4. version resolves from the canonical SDK version source

The existing `.gitea/workflows/sdk-package-release.yml` lane is valid proof input.

### Gate 2 - Canonical author path proof

Prove a minimal external extension created from the supported template can pass the author loop.

Required proof:
1. `python -m orket_extension_sdk.validate . --json`
2. `python -m orket_extension_sdk.import_scan src --json`
3. `orket ext validate . --strict --json`
4. the extension test suite passes

This proof must be shown from the external-extension template path, not only monorepo fixtures.

### Gate 3 - Fail-closed validation proof

Prove the host and SDK fail closed on the important drift cases.

Required proof cases:
1. unsupported `manifest_version`
2. missing manifest
3. invalid or missing entrypoint
4. disallowed internal `orket` imports
5. bad or unknown capabilities under strict mode

Current proof entrypoints already include:
1. `tests/interfaces/test_ext_validate_cli.py`
2. `tests/sdk/test_validate_module.py`
3. `tests/sdk/test_manifest.py`
4. `tests/sdk/test_import_scan_module.py`

### Gate 4 - Operator and author parity proof

Prove docs, template, and tooling tell one story.

Required proof:
1. commands in `CURRENT_AUTHORITY.md`
2. commands in `docs/guides/external-extension-authoring.md`
3. commands in `docs/templates/external_extension/README.md`
4. commands in `docs/templates/external_extension/.gitea/workflows/ci.yml`
5. actual CLI and SDK behavior

These must align in the same change.

### Gate 5 - No second authority proof

Prove validation does not silently become runtime authority.

Required proof:
1. a validated extension still remains subject to host-owned capability and runtime checks
2. docs and CLI wording do not imply that validation means trusted runtime authority
3. no codepath bypasses host governance because package validation succeeded

## Execution sequence

1. lock the canonical package shape and external author loop against current repo truth
2. align author docs, template docs, template CI, and SDK package proof around that one shape
3. prove fail-closed validation and package installability without widening runtime or publish scope
4. close the lane only when package surface, author path, operator path, and validation authority tell one cold story

## Completion bar

This lane is complete only when:
1. an external extension author has one supported build and validate path
2. an operator has one supported strict validation path
3. the package, install, and validate story is cold and consistent across docs, template, CLI, and SDK tools
4. Packet 1 boundaries remain explicit
5. publish and distribution concerns are still clearly deferred

## Stop conditions

Stop and narrow immediately if the lane starts absorbing:
1. package registry or marketplace design
2. SDK public release strategy beyond current proof needs
3. runtime seam extraction
4. new manifest family design
5. API or UI productization of extension validation
6. broad capability-system redesign
