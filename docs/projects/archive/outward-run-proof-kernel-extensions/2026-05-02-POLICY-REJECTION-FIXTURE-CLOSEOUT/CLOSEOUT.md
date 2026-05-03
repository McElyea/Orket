# Outward Run Policy-Rejection Fixture Closeout

Last updated: 2026-05-02
Status: Completed slice closeout
Owner: Orket Core

Requirements: `POLICY_REJECTION_FIXTURE_REQUIREMENTS_V1.md`
Implementation plan: `POLICY_REJECTION_FIXTURE_IMPLEMENTATION_PLAN.md`
Parent umbrella lane: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`

## Closed Boundary

This slice completed `outward_run_write_file_policy_rejected_v1` only.

The completed claim is:

```text
For outward_run_write_file_policy_rejected_v1, a model-produced write_file proposal was rejected by policy before approval or tool invocation, and no tool effect or commitment occurred after the policy rejection.
```

The fixture is real governed-run evidence from the normal outward submission, model proposal, connector-policy validation, policy rejection, and terminalization path. It is not hand-authored package evidence.

## Accepted Evidence

1. Frozen fixture: `tests/proof_fixtures/outward_run/base_policy_rejected_package/`
2. Live proof output: `benchmarks/results/proof/outward_write_file_policy_rejected_proof_run.json`
3. Policy-rejection verifier output: `benchmarks/results/proof/outward_run_policy_rejected_witness_report.json`
4. Corruption suite output: `benchmarks/results/proof/outward_run_corruption_report.json`
5. Assurance-case validation output: `benchmarks/results/proof/outward_run_assurance_case_validation.json`

## Accepted Commands

1. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_outward_write_file_policy_rejected_proof.py --json`
2. `python scripts/proof/verify_outward_run_witness_package.py --package tests/proof_fixtures/outward_run/base_policy_rejected_package --scope outward_run_write_file_policy_rejected_v1 --output benchmarks/results/proof/outward_run_policy_rejected_witness_report.json`
3. `python scripts/proof/run_outward_run_corruption_suite.py --output benchmarks/results/proof/outward_run_corruption_report.json`
4. `python scripts/proof/validate_outward_run_assurance_case.py --output benchmarks/results/proof/outward_run_assurance_case_validation.json`

## Completion Notes

The policy-rejection package includes package-local `manifest.json`, `outward_witness_bundle.json`, and full `ledger_export.json` bytes with `export_scope=all`.

The package omits `artifacts/committed_output`, approval authority, effect evidence, tool invocation evidence, and commitment evidence. The rejected proposal is correlated by `proposal_ref`.

`ORP-CORR-031` is now active over `base_policy_rejected_package` and rejects with `policy_rejected_proposal_invoked`.

## Remaining Scope

This closeout does not activate or complete:

1. out-of-scope proposal rejection;
2. multi-turn sequence proof;
3. ODR determinism integration;
4. claim posture widening;
5. public trust wording changes;
6. umbrella extension lane retirement.
