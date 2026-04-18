# Mathematical Foundation And Invariants Implementation Plan

Last updated: 2026-04-18
Status: Archived implementation lane
Owner: Orket Core

Accepted requirements archive: `docs/projects/archive/Proof/MFI04182026-IMPLEMENTATION-CLOSEOUT/MATHEMATICAL_FOUNDATION_AND_INVARIANTS_REQUIREMENTS.md`
Durable contract: `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
Dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`

## Purpose

Implement the accepted bounded invariant model for the ProductFlow Trusted Run Witness slice.

The implementation target is:

```text
If a verifier accepts a witness bundle for trusted_run_productflow_write_file_v1,
then the bundle passes the recomputed contract verdict and Trusted Run Invariants v1.
```

## Work Items

1. Extract the durable invariant contract to `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`.
2. Add a small `trusted_run_invariant_model.v1` evaluator under `scripts/proof/`.
3. Wire `verify_witness_bundle_payload` to fail closed on invariant failures and to include invariant proof output.
4. Wire campaign comparison to require stable invariant signatures before claiming `verdict_deterministic`.
5. Update ProductFlow witness fixture evidence so step lineage, lease source, resource consistency, effect prior chain, and final-truth cardinality are mechanically checked.
6. Add contract tests for legal traces, illegal traces, serialized corruptions, side-effect-free verifier behavior, and campaign signature stability.
7. Run structural, contract, live ProductFlow campaign, and docs hygiene proof.
8. Archive this lane when all gates pass.

## Completion Gate

This lane is complete only when:

1. every accepted invariant has a verifier check or explicit failure/blocker output
2. every named former missing-proof blocker is closed or visible in proof output
3. the negative corruption matrix is covered by tests or named as deferred
4. a single bundle remains `non_deterministic_lab_only`
5. a two-run campaign can claim `verdict_deterministic` only with stable verdict and invariant signatures
6. docs hygiene passes and no completed implementation plan remains active under `docs/projects/Proof/`
