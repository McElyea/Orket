# Effect Journal and Checkpoint Requirements
Last updated: 2026-03-23
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: Control-plane foundation / effect journal and checkpoint authority

## Purpose

Define the missing authority surface for:
1. effect publication and integrity
2. checkpoint admissibility and resumability

This document closes one of the implementation-gate gaps identified by the packet.

## Authority note

Shared enums and first-class object nouns are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

`EffectJournalEntry` and `CheckpointAcceptanceRecord` are first-class control-plane records in this lane.

## Core assertions

1. The effect journal is a normative authority surface, not a bag of receipts.
2. A checkpoint is not accepted merely because state was saved.
3. Recovery, replay, and reconciliation must consume journal and checkpoint truth without inventing hidden state.

## Effect journal requirements

### EJ-01. Effect journal authority

The control plane must publish effect truth through a durable effect journal that is:
1. append-only
2. ordered
3. integrity-verifiable
4. linked to authorization basis
5. linked to observed result and uncertainty class
6. usable as a reconciliation and replay input

### EJ-02. Journal entry minimum fields

Every effect journal entry must carry at minimum:
1. journal entry identifier
2. parent effect identifier
3. parent run, attempt, and step references
4. authorization basis reference
5. publication order index
6. publication timestamp
7. intended target reference
8. observed result reference
9. uncertainty class
10. integrity verification reference

### EJ-03. Ordered publication

The journal must provide a stable ordering surface strong enough that:
1. later reconciliation can explain effect order truthfully
2. replay can consume journal entries deterministically
3. superseding interpretation does not rewrite earlier publication order

### EJ-04. Authorization and observation linkage

The journal must preserve explicit linkage between:
1. what was authorized
2. what was attempted
3. what was observed
4. what remained uncertain

### EJ-05. Contradiction handling

The journal must not collapse contradictory evidence into a single success-like entry.

Where contradiction exists, later entries may:
1. supersede interpretation
2. publish reconciliation output
3. publish repair outcome

They must not erase earlier effect truth.

## Checkpoint requirements

### EJ-06. Checkpoint admissibility

A checkpoint is admissible only when the supervisor can verify:
1. integrity of the checkpoint record
2. policy compatibility
3. dependency status for resources and effects
4. required re-observation class
5. resumability class

### EJ-07. Checkpoint minimum fields

In addition to the `Checkpoint` object fields defined in the execution object model, checkpoint acceptance must publish:
1. acceptance or rejection result
2. accepting supervisor basis
3. required re-observation scope
4. dependent effect journal range or references
5. dependent reservation or lease references

### EJ-08. Checkpoint invalidation

A checkpoint must be invalidated when:
1. policy digest no longer matches
2. dependent resource truth diverges unsafely
3. dependent effect truth remains unresolved
4. integrity verification fails
5. a later recovery action explicitly supersedes it

### EJ-09. Resume semantics

Resume must be classified as one of:
1. `resume_same_attempt`
2. `resume_new_attempt_from_checkpoint`
3. `resume_forbidden`

The control plane must publish which one applies.

## Journal and checkpoint coupling

### EJ-10. No checkpoint hides effect uncertainty

A checkpoint must not be accepted as a shortcut that hides:
1. unresolved effect-boundary uncertainty
2. unresolved resource uncertainty
3. unresolved contradiction

### EJ-11. Recovery consumes journal and checkpoint truth

Recovery decisions that involve resume or partial replay must reference:
1. the relevant checkpoint
2. the relevant journal range or entry set
3. the resulting residual uncertainty class

### EJ-12. Reconciliation consumes journal truth

Reconciliation must treat the effect journal as a primary authority surface for intended and attempted effect history.

## Acceptance criteria

This document is acceptable only when:
1. effect journal truth is stronger than ad hoc receipt storage
2. checkpoint acceptance is supervisor-owned and policy-governed
3. replay and reconciliation can consume both surfaces directly
4. contradiction and uncertainty remain visible instead of being rewritten away
