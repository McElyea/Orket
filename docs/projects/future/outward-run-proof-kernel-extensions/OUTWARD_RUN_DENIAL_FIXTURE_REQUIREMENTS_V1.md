# Outward Run Denial Fixture Requirements v1

Last updated: 2026-05-02
Status: Accepted requirements - active implementation plan
Owner: Orket Core

Implementation plan: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_DENIAL_FIXTURE_IMPLEMENTATION_PLAN.md`
Base closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/`

## Acceptance Record

The user explicitly requested on 2026-05-02 that Codex pick one scoped outward proof-kernel extension target, write requirements, accept that requirements scope, build the implementation plan, and move the plan into `Priority Now`.

Codex selected and accepts only the denial fixture target for implementation. This acceptance does not include policy-rejection, out-of-scope, multi-turn, ODR, public-trust, or posture-widening work.

## Purpose

Create a real governed denial-path witness package and make the offline verifier accept the bounded claim:

```text
For outward_run_write_file_denied_v1, a model-produced write_file proposal was admitted for human review, denied through the normal approval surface, and no tool effect or commitment occurred after denial.
```

## Scope

Target compare scope: `outward_run_write_file_denied_v1`

In scope:
1. produce `tests/proof_fixtures/outward_run/base_denied_package/` from a real outward governed run;
2. use the normal outward submission, proposal, approval-denial, and terminalization path;
3. require a full packaged `ledger_export.v1` with `export_scope=all`;
4. prove `proposal_denied` before terminal run truth;
5. prove absence of `tool_invoked` and `commitment_recorded` events for the denied approval id;
6. accept denial packages from package bytes only, never bundle-only JSON;
7. activate ORP-INV-013 for accepted denial evidence;
8. activate denial-side absence checks under ORP-INV-022;
9. activate ORP-CORR-030, and the denial side of ORP-CORR-068 if the implemented corruption can stay package-only and deterministic.

Out of scope:
1. policy-rejection fixture generation;
2. out-of-scope proposal fixture generation;
3. multi-turn sequence proof;
4. ODR determinism integration;
5. claim posture above `outward_lab_only`;
6. public trust wording changes;
7. proving model output semantics.

## Evidence Requirements

DEN-REQ-001: The package producer must originate denial evidence from persisted outward run records, approval records, full ledger export bytes, model evidence, and denial terminal truth from the normal outward path.

DEN-REQ-002: The package must not fabricate `artifacts/committed_output` when no committed effect exists. Denial packages may omit committed artifact refs only when the verifier is evaluating `outward_run_write_file_denied_v1`.

DEN-REQ-003: The verifier must reject any denial package that contains a `tool_invoked` or `commitment_recorded` event after `proposal_denied` for the same approval id.

DEN-REQ-004: Absence claims must require full `ledger_export.v1` bytes with `export_scope=all`.

DEN-REQ-005: Denial proof acceptance must remain side-effect-free and package-local.

DEN-REQ-006: The denial fixture must be labeled as real governed-run evidence only if it was captured from normal outward submission and denial handling; otherwise it must remain synthetic and ineligible for closeout.

DEN-REQ-007: The approved-path proof kernel must remain green while the denial path is added.

## Required Contract Deltas

The implementation must update active outward proof specs in the same change before code treats denial evidence as accepted authority:

1. `docs/specs/OUTWARD_RUN_WITNESS_V1.md` must admit the denial package shape and clarify when committed artifact bytes are not required.
2. `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md` must mark ORP-INV-013 and ORP-INV-022 active for `outward_run_write_file_denied_v1`.
3. `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md` must keep a single accepted denial package capped at `outward_lab_only`.
4. `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md` must remain compatible with package-consuming denial assurance rows.

## Stop Conditions

Stop and report a blocker instead of accepting the denial path if:
1. the denial package is hand-authored or synthetic;
2. the verifier needs a live database, API, provider, clock, network, process environment policy, or mutable workspace path;
3. absence is claimed without full `export_scope=all` ledger bytes;
4. the package contains effect evidence for the denied approval id;
5. denial acceptance would require weakening approved-path invariant checks; or
6. public trust wording would need to change.
