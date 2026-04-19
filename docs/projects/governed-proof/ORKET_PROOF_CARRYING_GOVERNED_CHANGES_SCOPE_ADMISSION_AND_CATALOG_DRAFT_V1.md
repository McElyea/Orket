# Orket Proof-Carrying Governed Changes Scope Admission And Catalog Draft v1

Last updated: 2026-04-18
Status: Active lane companion
Owner: Orket Core

Implementation lane: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`
Accepted requirements: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_REQUIREMENTS_V1.md`
Durable family authority:
1. `docs/specs/TRUSTED_CHANGE_SCOPE_ADMISSION_STANDARD_V1.md`
2. `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`

## Purpose

Preserve non-authoritative lane-local staging notes after the trusted change scope admission standard and admitted-scope catalog moved into durable authority under `docs/specs/`.

## Boundary

This document is not durable scope authority.

It does not:
1. admit a new scope,
2. replace `docs/specs/TRUSTED_CHANGE_SCOPE_ADMISSION_STANDARD_V1.md`,
3. replace `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`, or
4. act as public trust wording.

## Current Lane-Local Staging Notes

1. The durable admission checklist now lives in `docs/specs/TRUSTED_CHANGE_SCOPE_ADMISSION_STANDARD_V1.md`.
2. The durable admitted-scope catalog and scope cards now live in `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`.
3. The current internal admitted compare-scope set remains `trusted_run_productflow_write_file_v1`, `trusted_repo_config_change_v1`, and `trusted_terraform_plan_decision_v1`.
4. The current externally publishable public trust slice remains only `trusted_repo_config_change_v1`.
5. No additional governed-proof compare scope is currently staged for admission beyond the scopes already cataloged under durable authority.
6. Any future candidate remains lane-local only until a scope-local contract, catalog update, and `CURRENT_AUTHORITY.md` update land in the same change.

## Historical Note

The earlier draft-only checklist, catalog shape, and scope-card shape from this companion were promoted into durable authority on 2026-04-18.
