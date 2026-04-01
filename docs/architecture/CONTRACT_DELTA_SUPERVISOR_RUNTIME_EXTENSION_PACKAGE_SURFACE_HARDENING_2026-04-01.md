# Contract Delta: SupervisorRuntime extension package surface hardening

Last updated: 2026-04-01

## Metadata
- Change title: SupervisorRuntime Packet 1 external extension package surface hardening closeout
- Date: 2026-04-01
- Owners: Orket Core
- Related roadmap authority:
  - `docs/projects/archive/Extensions/EX04012026-PACKAGE-SURFACE-HARDENING-CLOSEOUT/EXTENSION_PACKAGE_SURFACE_HARDENING_IMPLEMENTATION_PLAN.md`

## Summary

The durable extension-validation contract already selected one manifest family and one host validation command.
This delta hardens the missing package surface around that validation seam so the SDK package, template, author guide, and operator path describe one cold Packet 1 external-extension story.

## Before

Before this change:
1. the active spec set described validation without one separate durable package-surface contract
2. template docs and template CI still advertised non-strict validation commands
3. template bootstrap assumed package-index availability for `orket-extension-sdk`
4. template validation scripts silently skipped host validation when `orket` was unavailable
5. host validation import scanning walked the whole extension root, so local virtualenv trees could distort scan scope
6. the SDK package release smoke import could look green from the repo root without proving separation from the main `orket` package

## After

After this change:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md` defines one canonical external package shape, bootstrap contract, author loop, and operator path
2. the canonical author and operator validation paths are strict-only and aligned across the author guide, template README, template CI, and template scripts
3. template bootstrap now requires explicit `ORKET_SDK_INSTALL_SPEC` and, when needed, `ORKET_HOST_INSTALL_SPEC` instead of assuming publish
4. template validation now fails closed when the host CLI is unavailable instead of silently skipping host validation
5. host validation import scanning uses `src/` when present and ignores local virtualenv or vendor trees so the scan stays about extension source
6. the SDK package release smoke import now runs outside the repo root so the installable-package proof does not accidentally inherit the monorepo on `sys.path`

## Required same-change updates

1. add `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
2. update `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
3. update `docs/guides/external-extension-authoring.md`
4. update `docs/templates/external_extension/README.md`
5. update `docs/templates/external_extension/.gitea/workflows/ci.yml`
6. update `CURRENT_AUTHORITY.md`
7. update `docs/RUNBOOK.md`
8. archive the completed Extensions lane and remove the active roadmap entry

## Verification notes

Primary proof for the hardened package surface:
1. `python -m pytest -q tests/interfaces/test_ext_validate_cli.py tests/sdk/test_validate_module.py tests/sdk/test_manifest.py tests/sdk/test_import_scan_module.py`
2. `python -m build --sdist --wheel ./orket_extension_sdk`
3. clean-environment SDK wheel install smoke outside the repo root
4. clean-environment template bootstrap plus strict author-path proof from a copied external template repository
