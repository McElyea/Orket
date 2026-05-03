# Outward Run Policy-Rejection Fixture Requirements v1

Last updated: 2026-05-02
Status: Active accepted requirements
Owner: Orket Core

Implementation plan: `docs/projects/archive/outward-run-proof-kernel-extensions/2026-05-02-POLICY-REJECTION-FIXTURE-CLOSEOUT/POLICY_REJECTION_FIXTURE_IMPLEMENTATION_PLAN.md`
Parent umbrella lane: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`
Base closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/`
Completed denial closeout: `docs/projects/archive/outward-run-proof-kernel-extensions/2026-05-02-DENIAL-FIXTURE-CLOSEOUT/`

## Acceptance Record

The user explicitly requested on 2026-05-02 that the outward proof-kernel extensions lane reopen only for policy-rejection fixture implementation, with a slice-scoped active plan and a roadmap entry pointing to that plan.

This requirements document accepts only the policy-rejection fixture target for implementation. It does not accept out-of-scope proposal rejection, multi-turn sequence proof, ODR determinism, claim posture widening, public trust wording, or retirement of the umbrella extension lane.

## Purpose

Create a real governed policy-rejection witness package and make the offline proof kernel accept the bounded claim:

```text
For outward_run_write_file_policy_rejected_v1, a model-produced write_file proposal was rejected by policy before approval or tool invocation, and no tool effect or commitment occurred after the policy rejection.
```

## Scope

Target compare scope: `outward_run_write_file_policy_rejected_v1`

This slice covers an admitted `write_file` governed-tool proposal whose args fail `write_file` policy validation, such as workspace containment. It does not cover a model proposing an unadmitted tool, unknown tool, or non-contract tool family; that remains the deferred out-of-scope proposal fixture.

In scope:
1. produce `tests/proof_fixtures/outward_run/base_policy_rejected_package/` from a real outward governed run;
2. use the normal outward submission, model proposal, policy rejection, and terminalization path;
3. require a full packaged `ledger_export.v1` with `export_scope=all`;
4. prove `proposal_policy_rejected` before terminal run truth;
5. prove absence of `proposal_approved`, `tool_invoked`, and `commitment_recorded` events for the rejected proposal identity;
6. accept policy-rejection packages from package bytes only, never bundle-only JSON;
7. activate ORP-INV-014 and policy-rejection-side ORP-INV-022;
8. activate ORP-CORR-031 as a falsifiable corruption over a real policy-rejection fixture.

Out of scope:
1. out-of-scope proposal fixture generation;
2. unknown, unadmitted, or non-contract tool-family proposal rejection;
3. multi-turn sequence proof;
4. ODR determinism integration;
5. claim posture above `outward_lab_only`;
6. public trust wording changes;
7. proving model output semantics.

## Proposal Identity

Policy-rejected proposals must be correlated by the tuple:

```text
(run_id, turn, tool_name, tool_args_hash)
```

Package evidence should expose this as:

```text
proposal_ref = "model_proposal:<run_id>:<turn>:<tool_name>:<tool_args_hash>"
```

The verifier may read the tuple directly for legacy package evidence, but accepted policy-rejection package output must carry a stable `proposal_ref`.

## Evidence Requirements

PRF-REQ-001: The package producer must originate policy-rejection evidence from persisted outward run records, full ledger export bytes, model evidence, policy authority evidence, and terminal truth from the normal outward path.

PRF-REQ-002: The package must not fabricate `artifacts/committed_output` when no committed effect exists. Policy-rejection packages may omit committed artifact refs only when the verifier is evaluating `outward_run_write_file_policy_rejected_v1`.

PRF-REQ-003: The package must not contain approval authority for the policy-rejected proposal identity.

PRF-REQ-004: The verifier must reject any policy-rejection package that contains a `tool_invoked` event after `proposal_policy_rejected` for the same proposal identity with `policy_rejected_proposal_invoked`.

PRF-REQ-005: The verifier must reject any policy-rejection package that contains a `commitment_recorded` event after `proposal_policy_rejected` for the same proposal identity with `policy_rejected_proposal_committed`.

PRF-REQ-006: Absence claims must require full `ledger_export.v1` bytes with `export_scope=all`.

PRF-REQ-007: Policy-rejection proof acceptance must remain side-effect-free and package-local.

PRF-REQ-008: The policy-rejection fixture must be labeled as real governed-run evidence only if it was captured from normal outward submission and policy handling; otherwise it must remain synthetic and ineligible for closeout.

PRF-REQ-009: The approved-path and denial-path proof kernels must remain green while the policy-rejection path is added.

## Required Contract Deltas

The implementation must update active outward proof specs in the same change before code treats policy-rejection evidence as accepted authority:

1. `docs/specs/OUTWARD_RUN_WITNESS_V1.md` must admit the policy-rejection package shape and clarify when committed artifact bytes and approval authority are not required.
2. `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md` must mark ORP-INV-014 and policy-rejection-side ORP-INV-022 active for `outward_run_write_file_policy_rejected_v1`, including `policy_rejected_proposal_committed`.
3. `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md` must keep a single accepted policy-rejection package capped at `outward_lab_only`.
4. `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md` must remain compatible with package-consuming policy-rejection assurance rows.

## Stop Conditions

Stop and report a blocker instead of accepting the policy-rejection path if:
1. the package is hand-authored or synthetic;
2. the verifier needs a live database, API, provider, clock, network, process environment policy, or mutable workspace path;
3. absence is claimed without full `export_scope=all` ledger bytes;
4. the package contains approval, effect, or commitment evidence for the rejected proposal identity;
5. policy-rejection acceptance would require weakening approved-path or denial-path invariant checks;
6. the only available rejection path is an unknown, unadmitted, or non-contract tool-family proposal;
7. public trust wording would need to change.
