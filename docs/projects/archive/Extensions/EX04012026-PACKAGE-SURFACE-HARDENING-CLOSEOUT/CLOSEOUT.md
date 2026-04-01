# Extension Package Surface Hardening Closeout

Last updated: 2026-04-01
Status: Archived
Owner: Orket Core

## Summary

The bounded Extension Package Surface Hardening lane is complete.

Packet 1 now has one durable external-extension package story across:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
3. `docs/guides/external-extension-authoring.md`
4. `docs/templates/external_extension/README.md`
5. `docs/templates/external_extension/.gitea/workflows/ci.yml`
6. template bootstrap and validation scripts
7. SDK and host validation seams

## What shipped

1. one canonical Packet 1 external extension package shape rooted at `pyproject.toml`, one manifest, `src/`, `tests/`, and `scripts/`
2. one canonical bootstrap contract using explicit `ORKET_SDK_INSTALL_SPEC` and optional `ORKET_HOST_INSTALL_SPEC`
3. one canonical strict author loop:
   1. SDK strict validate
   2. SDK import scan
   3. strict host validate
   4. tests
4. one canonical operator path: `orket ext validate <extension_root> --strict --json`
5. one explicit package and manifest relationship, including version alignment
6. one source-scoped import-isolation rule so host validation scans `src/` when present instead of unrelated local virtualenv trees
7. one truthful SDK package smoke proof that runs outside the repo root

## Explicit non-goals still deferred

1. publish or distribution hardening
2. registry or marketplace behavior
3. new manifest families
4. runtime authority expansion derived from validation success
5. API or UI productization of extension validation

## Proof summary

Observed path: `primary`
Observed result: `success`
Proof type: live

Completed proof:
1. `python -m pytest -q tests/interfaces/test_ext_validate_cli.py tests/interfaces/test_ext_init_cli.py tests/sdk/test_validate_module.py tests/sdk/test_manifest.py tests/sdk/test_import_scan_module.py docs/templates/external_extension/tests/test_manifest_validation.py`
2. `python -m build --sdist --wheel ./orket_extension_sdk --outdir .tmp/sdk-package-gate`
3. clean-environment SDK wheel install smoke outside the repo root with `orket_present=False`
4. clean-environment copied-template bootstrap through `scripts/install.ps1` plus strict author-loop proof through `scripts/validate.ps1`
5. `python scripts/governance/check_docs_project_hygiene.py`

## Remaining future reopen

If extension work is reopened next, the truthful next lane is publish-surface hardening only.
Package-surface hardening is complete and should not be reopened unless contract drift or proof failure is discovered.
