# Control Plane As Witness Substrate

Last updated: 2026-04-18
Status: Implemented and archived
Authority status: Historical staging source only. Completed lane archive lives at `docs/projects/archive/Proof/CPWS04182026-IMPLEMENTATION-CLOSEOUT/`.
Owner: Orket Core

## Current Shipped Baseline

`CURRENT_AUTHORITY.md` records a large current control-plane surface across selected run, reservation, lease, checkpoint, approval, effect, reconciliation, and final-truth paths.

`docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md` locks the governed workload start-path authority and names which start paths are catalog-resolved, projection-resolved, or routing-only.

The current baseline is powerful but uneven:

1. control-plane authority is not universal
2. effect-journal publication is not the default truth path everywhere
3. governed turn-tool namespace enforcement is stronger than many other runtime paths
4. broader supervisor-owned checkpoint creation is still partial

## Future Delta Proposed By This Doc

Treat the control plane as a witness substrate rather than the next product surface to expand.

The control plane should advance only where a selected workflow needs a stronger witness bundle.

The next control-plane work should be justified by one of these questions:

1. Does this record family make the trusted-run witness verifiable?
2. Does this invariant prevent false success?
3. Does this projection remove duplicate authority?
4. Does this proof surface make missing evidence explicit?

If the answer is no, the work probably belongs later.

## What This Doc Does Not Reopen

1. It does not reopen the archived ControlPlane project.
2. It does not authorize repo-wide convergence work.
3. It does not require every runtime path to become governed before a useful proof lane can ship.
4. It does not make read-model convenience projections authoritative.
5. It does not add new record families without a selected proof need.

## Problem

The control plane can get ahead of the things it controls when the runtime has more authority nouns than user-visible proof.

That creates three risks:

1. users cannot tell which paths are actually governed
2. contributors keep adding authority records without a bounded product claim
3. docs begin to imply universal truth before implementation and proof support it

## Proposed Operating Rule

For the proof packet, control-plane work should follow this rule:

```text
No new authority noun without a verifier question it answers.
```

Examples:

1. `RunRecord` answers which governed run was admitted.
2. `CheckpointRecord` answers where continuation was allowed or forbidden.
3. `ReservationRecord` and `LeaseRecord` answer who owned the namespace or resource.
4. `EffectJournalEntryRecord` answers what effect was authorized and observed.
5. `FinalTruthRecord` answers the terminal result classification.

## Witness-Required Record Families

The first trusted-run witness should require only the record families needed for a small governed mutation:

1. workload record or workload projection
2. resolved policy snapshot
3. resolved configuration snapshot
4. run record
5. attempt record
6. step record
7. checkpoint and checkpoint acceptance records when approval continuation occurs
8. reservation and lease records for the governed namespace or resource
9. operator action record for approval or denial
10. effect journal entry records for observed effects
11. final truth record

Everything else should be optional or explicitly out of scope for the first slice.

## Read Model Rule

Read models and review packages may summarize witness evidence, but they must not become co-equal authority.

Every convenience summary should preserve:

1. source record refs
2. projection-only framing where applicable
3. missing-evidence markers
4. claim-tier boundaries

## Acceptance Boundary

This idea is ready for implementation when a selected trusted-run slice has a record-family matrix with:

1. required records
2. optional records
3. forbidden substitutes
4. verifier checks
5. failure semantics for missing or contradictory records
