# Mathematical Foundation And Invariants

Last updated: 2026-04-18
Status: Implemented and archived
Authority status: Historical staging source only. Completed lane archive lives at `docs/projects/archive/Proof/MFI04182026-IMPLEMENTATION-CLOSEOUT/`.
Owner: Orket Core

## Current Shipped Baseline

Orket already has a target architecture built around deterministic runtime state transitions:

```text
next_state = deterministic_transition(current_state, input_event)
```

The current invariant and proof-related authorities include:

1. `docs/ARCHITECTURE.md`
2. `docs/specs/RUNTIME_INVARIANTS.md`
3. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
4. `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
5. control-plane Pydantic models under `orket/core/contracts/`

These are strong foundations, but they are not a formal proof that the full Python runtime is correct.

## Future Delta Proposed By This Doc

Define a small formal model for the trusted-run witness surface.

The model should prove bounded claims such as:

```text
If a verifier accepts a trusted-run witness bundle,
then the recorded trace satisfies the declared trusted-run invariants
for the named compare scope.
```

This is narrower and more truthful than claiming Orket is mathematically sound as a whole.

## What This Doc Does Not Reopen

1. It does not claim full formal verification of Orket.
2. It does not require proving model-generated text is correct.
3. It does not require proving all runtime paths.
4. It does not replace live proof, integration proof, or contract proof.
5. It does not weaken existing fail-closed runtime behavior.

## Formal Core

The first formal core should model a finite state machine for:

1. run lifecycle
2. attempt lifecycle
3. checkpoint acceptance
4. approval hold and approval resolution
5. reservation to lease promotion
6. effect journal publication
7. final truth publication

The model should be small enough to express as:

```text
State:
  runs
  attempts
  checkpoints
  reservations
  leases
  operator_actions
  effects
  final_truth

Transition:
  admit_run
  start_attempt
  publish_checkpoint
  request_approval
  resolve_approval
  promote_reservation_to_lease
  publish_effect
  publish_final_truth
  block_or_fail_closed
```

## Core Invariants

The first invariant set should include:

1. A successful final truth record requires sufficient evidence.
2. A terminal run has one terminal final truth authority.
3. A final truth record must reference a known run.
4. An effect journal entry must reference a known run, attempt, and step.
5. A non-initial effect journal entry must link to a prior entry.
6. Approval continuation must bind to the same governed run and accepted checkpoint.
7. A promoted lease must have a source reservation.
8. A namespace mutation must not proceed when current resource authority disagrees with the active lease.
9. Missing required evidence cannot produce a success claim.
10. Replay or verification must not mutate durable runtime state.

## Proof Method

Start with a pragmatic proof stack:

1. model-level state machine checks
2. property-based trace generation for legal and illegal traces
3. verifier checks over serialized witness bundles
4. contract tests that corrupt one required field at a time
5. live or integration proof for the selected run slice

This is not theorem-prover purity.
It is an engineering proof stack that makes false success harder to ship.

## Candidate Artifacts

Future work can introduce:

1. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
2. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
3. a verifier schema for trusted-run bundles
4. property-based tests for trace validity
5. corruption fixtures for verifier negative proof

## Acceptance Boundary

This idea becomes useful when:

1. the formal model is smaller than the implementation
2. each model invariant maps to at least one verifier check
3. each verifier check has at least one negative corruption test
4. the accepted claim names its compare scope
5. the proof report states exactly what remains outside the model
