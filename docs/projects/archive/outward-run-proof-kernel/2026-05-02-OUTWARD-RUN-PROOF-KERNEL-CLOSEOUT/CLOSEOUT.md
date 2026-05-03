# Outward Run Proof Kernel Closeout

Last updated: 2026-05-02
Status: Archived approved single-turn closeout
Owner: Orket Core

## Completed Boundary

This archive closes only the approved single-turn `outward_run_write_file_approved_v1` proof kernel boundary:

1. package producer,
2. offline package verifier,
3. ledger and committed-artifact validation,
4. approved-path invariant checker,
5. approved-path corruption suite,
6. claim-tier enforcement for the accepted package posture, and
7. assurance-case schema validation for the approved boundary with explicit path-family blockers.

Active durable authority for that completed boundary lives in:

1. `docs/specs/OUTWARD_RUN_WITNESS_V1.md`,
2. `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md`,
3. `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md`,
4. `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md`, and
5. `CURRENT_AUTHORITY.md`.

## Future Work Split

Undone extension work is not closed by this archive. It has been moved to `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`.

That future lane owns:

1. denial, policy-rejection, and out-of-scope package fixtures,
2. absence-claim corruption paths that require those fixtures,
3. multi-turn sequence proof,
4. ODR determinism integration, and
5. any posture widening beyond the evidence-supported approved-path boundary.

## Accepted Verification

The accepted closeout commands are:

1. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_outward_write_file_approved_proof.py`,
2. `python scripts/proof/verify_outward_run_witness_package.py --package benchmarks/results/proof/outward_run_witness_package.v1 --scope outward_run_write_file_approved_v1 --output benchmarks/results/proof/outward_run_witness_report.json`,
3. `python scripts/proof/validate_outward_write_file_committed.py --package benchmarks/results/proof/outward_run_witness_package.v1 --output benchmarks/results/proof/outward_write_file_validation.json`,
4. `python scripts/proof/run_outward_run_corruption_suite.py --base benchmarks/results/proof/outward_run_witness_package.v1 --output benchmarks/results/proof/outward_run_corruption_report.json`, and
5. `python scripts/proof/validate_outward_run_assurance_case.py --output benchmarks/results/proof/outward_run_assurance_case_validation.json`.

This closeout does not widen public trust wording and does not claim a whole-runtime mathematical proof.
