# Contract Delta: Trusted Change Scope Family Authority

## Summary
- Change title: Trusted change scope family admission standard and catalog promotion
- Owner: Orket Core
- Date: 2026-04-18
- Affected contract(s): `docs/specs/TRUSTED_CHANGE_SCOPE_ADMISSION_STANDARD_V1.md`, `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`, `docs/specs/TRUSTED_RUN_WITNESS_V1.md`, `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`, `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`, `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_SCOPE_ADMISSION_AND_CATALOG_DRAFT_V1.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: trusted change scope admission and compare-scope catalog rules lived only in the governed-proof lane draft, while the shared validator-backed family helper existed in code without durable family authority naming it.
- Proposed behavior: publish one durable scope-admission standard and one durable admitted-scope catalog under `docs/specs/`, keep the lane draft non-authoritative, and record the shared validator-backed helper boundary in current authority.
- Why this break is required now: Workstream 4 requires repeatable scope admission across more than one effect class without leaving the family story trapped in lane-local project docs.

## Migration Plan
1. Compatibility window: immediate; admitted compare scopes and canonical proof commands remain unchanged.
2. Migration steps:
   1. add the durable admission-standard and catalog specs under `docs/specs/`,
   2. reduce the lane-local draft to a non-authoritative staging companion,
   3. update the governed-proof implementation plan and `CURRENT_AUTHORITY.md` in the same change.
3. Validation gates:
   1. `python -m pytest -q tests/scripts/test_trusted_scope_family_support.py tests/scripts/test_first_useful_workflow_slice.py tests/scripts/test_trusted_terraform_plan_decision.py tests/scripts/test_offline_trusted_run_verifier.py`
   2. `python scripts/governance/check_docs_project_hygiene.py`
   3. diff-check over the touched docs and test surfaces

## Rollback Plan
1. Rollback trigger: the durable family catalog or admission standard drifts from current admitted scope truth, or the named helper boundary no longer reflects the actual validator-backed scope implementation.
2. Rollback steps:
   1. remove the durable family specs,
   2. restore the lane draft as the only staging surface,
   3. remove the family-authority additions from `CURRENT_AUTHORITY.md`.
3. Data/state recovery notes: no durable workflow state migration is required; this change affects durable documentation authority and test coverage only.

## Versioning Decision
- Version bump type: additive family-authority extraction
- Effective version/date: 2026-04-18
- Downstream impact: trusted-run and governed-proof readers now have one durable admission standard and one durable admitted-scope catalog instead of depending on lane-local draft prose.
