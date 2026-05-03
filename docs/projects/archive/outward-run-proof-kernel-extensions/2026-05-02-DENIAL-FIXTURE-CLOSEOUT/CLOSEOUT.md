# Outward Run Denial Fixture Closeout

Last updated: 2026-05-02
Status: Archived closeout
Owner: Orket Core

## Closed Boundary

This archive closes only the `outward_run_write_file_denied_v1` single-turn denial package boundary.

Accepted evidence:
1. a normal outward submission reached approval-required state;
2. the proposal was denied through `OutwardApprovalService.deny`;
3. denial terminalization produced no `tool_invoked` and no `commitment_recorded` event;
4. the package verifier accepted the frozen package from package-local bytes only;
5. ORP-CORR-030 and the denial side of ORP-CORR-068 are falsifiable over the denial fixture.

## Canonical Artifacts

1. Requirements: `OUTWARD_RUN_DENIAL_FIXTURE_REQUIREMENTS_V1.md`
2. Implementation plan: `OUTWARD_RUN_DENIAL_FIXTURE_IMPLEMENTATION_PLAN.md`
3. Frozen fixture: `tests/proof_fixtures/outward_run/base_denied_package/`
4. Active specs: `docs/specs/OUTWARD_RUN_WITNESS_V1.md`, `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md`, `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md`, and `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md`

## Verification Record

Observed path: `primary`

Observed result: `success`

Commands:
1. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_outward_write_file_denied_proof.py --package-output tests/proof_fixtures/outward_run/base_denied_package --json`
2. `python scripts/proof/verify_outward_run_witness_package.py --package tests/proof_fixtures/outward_run/base_denied_package --scope outward_run_write_file_denied_v1 --output benchmarks/results/proof/outward_run_denied_witness_report.json --json`
3. `python -m pytest -q tests/scripts/test_outward_run_witness_package.py tests/scripts/test_emit_outward_run_witness_package.py tests/scripts/test_outward_run_invariant_checker.py tests/scripts/test_verify_outward_run_witness_package.py tests/scripts/test_corrupt_outward_run_witness_package.py tests/contract/proof/test_outward_run_denial_package_fixture.py tests/contract/proof/test_outward_run_corruption_suite.py tests/application/test_outward_run_execution_service.py`

## Remaining Future-Hold Work

Policy-rejection, out-of-scope proposal rejection, multi-turn proof, ODR determinism, public trust wording, and posture-widening work remain outside this closeout.
