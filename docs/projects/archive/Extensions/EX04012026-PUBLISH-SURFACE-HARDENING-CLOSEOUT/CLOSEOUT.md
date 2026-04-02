# Extension Publish Surface Hardening Closeout

Last updated: 2026-04-01
Status: Archived
Owner: Orket Core

## Summary

The bounded Extension Publish Surface Hardening lane is complete.

Packet 1 now has one durable external-extension publish story across:
1. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
3. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
4. `docs/guides/external-extension-authoring.md`
5. `docs/templates/external_extension/README.md`
6. `docs/templates/external_extension/.gitea/workflows/ci.yml`
7. `docs/templates/external_extension/.gitea/workflows/release.yml`
8. template build and verify scripts plus the release-checker contract test
9. `CURRENT_AUTHORITY.md`

## What shipped

1. one authoritative published artifact family: `dist/<normalized_project_name>-<version>.tar.gz`
2. one canonical version-and-tag authority rule spanning `pyproject.toml`, manifest `extension_version`, built artifact naming, and release tag `v<extension_version>`
3. one canonical maintainer build-and-verify path through `scripts/build-release.*` and `scripts/verify-release.*`
4. one canonical tagged automation path through `docs/templates/external_extension/.gitea/workflows/release.yml`
5. one canonical operator intake path that extracts the authoritative source distribution and returns to `orket ext validate <extension_root> --strict --json`
6. one fail-closed release checker that rejects version, tag, manifest, entrypoint, and source-distribution layout drift
7. one explicit boundary that publish success and validation success remain admissibility evidence only and do not grant runtime authority

## Proof summary

Observed path: `primary`
Observed result: `success`
Proof type: `live`

Completed proof:
1. `python -m pytest -q tests/interfaces/test_ext_init_cli.py tests/interfaces/test_ext_validate_cli.py tests/application/test_check_extension_release_script.py`
2. `python -m pytest -q docs/templates/external_extension/tests/test_manifest_validation.py`
3. clean-environment copied-template maintainer proof through `scripts/install.ps1`, `scripts/validate.ps1`, `scripts/build-release.ps1`, and `scripts/verify-release.ps1 v0.1.0`
4. operator intake proof from extracted `dist/orket_companion_template-0.1.0.tar.gz` back through `orket ext validate . --strict --json`
5. `python scripts/governance/check_docs_project_hygiene.py`

## Remaining future reopen

1. registry, marketplace, discovery, and cloud-distribution work remain explicitly deferred
2. future extension publish or distribution work now requires an explicit new roadmap lane instead of reopening this completed Packet 1 publish surface implicitly
