# Orket Proof Packet Guide

Last updated: 2026-04-18
Status: Archived proof packet
Authority status: Historical archive only. Not roadmap authority. Not execution authority.
Owner: Orket Core

## Purpose

Preserve the proof-centered next-direction ideas that seeded the completed Proof lanes.

This packet existed because Orket's control plane was already strong enough to risk becoming the product story by itself. The next useful move was to make the control plane prove one externally useful workflow instead of expanding it as a universal ambition.

## Source Authorities

1. `docs/ARCHITECTURE.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
4. `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
5. `docs/specs/RUNTIME_INVARIANTS.md`
6. `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`
7. `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`
8. `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`

## Historical Posture

This packet was not a claim that Orket was mathematically proven.

It was not an active implementation plan.
It was not a roadmap entry.
It did not reopen ControlPlane, ProductFlow, Graphs, RuntimeOS, or any archived lane by implication.

Each child doc started as a candidate idea that could later be promoted into requirements, implementation, proof, or publication work only through explicit roadmap adoption.

`01_TRUSTED_RUN_WITNESS_RUNTIME.md` was promoted, accepted, implemented, and archived under `docs/projects/archive/Proof/`.

`03_MATHEMATICAL_FOUNDATION_AND_INVARIANTS.md` was promoted, accepted, implemented, and archived at `docs/projects/archive/Proof/MFI04182026-IMPLEMENTATION-CLOSEOUT/`.

`02_CONTROL_PLANE_AS_WITNESS_SUBSTRATE.md` was promoted, accepted, implemented, and archived at `docs/projects/archive/Proof/CPWS04182026-IMPLEMENTATION-CLOSEOUT/`.

`04_OFFLINE_VERIFIER_AND_CLAIM_LADDER.md` was promoted, accepted, implemented, and archived at `docs/projects/archive/Proof/OVCL04182026-IMPLEMENTATION-CLOSEOUT/`.

`05_FIRST_USEFUL_WORKFLOW_SLICE.md` was promoted, accepted, implemented, and archived at `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/`.

`06_TRUST_REASON_AND_EXTERNAL_ADOPTION.md` was promoted, accepted, implemented, and archived at `docs/projects/archive/Proof/TRAD04182026-IMPLEMENTATION-CLOSEOUT/`.

All child docs in this packet were eventually promoted and archived.

## Core Direction

The proposed direction is:

```text
Orket should become a verifiable workflow witness runtime.
```

That means Orket should make the following portable and machine-checkable for a bounded workflow:

1. what was requested
2. what authority admitted it
3. what runtime path executed
4. what approval, lease, checkpoint, and effect evidence exists
5. what terminal truth was assigned
6. whether replay or stability is proven
7. where proof stops when evidence is missing

## Packet Index

1. `01_TRUSTED_RUN_WITNESS_RUNTIME.md`
   - implementation archive: `docs/projects/archive/Proof/TRW04162026-IMPLEMENTATION-CLOSEOUT/`
2. `02_CONTROL_PLANE_AS_WITNESS_SUBSTRATE.md`
   - implementation archive: `docs/projects/archive/Proof/CPWS04182026-IMPLEMENTATION-CLOSEOUT/`
3. `03_MATHEMATICAL_FOUNDATION_AND_INVARIANTS.md`
   - implementation archive: `docs/projects/archive/Proof/MFI04182026-IMPLEMENTATION-CLOSEOUT/`
4. `04_OFFLINE_VERIFIER_AND_CLAIM_LADDER.md`
   - implementation archive: `docs/projects/archive/Proof/OVCL04182026-IMPLEMENTATION-CLOSEOUT/`
5. `05_FIRST_USEFUL_WORKFLOW_SLICE.md`
   - implementation archive: `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/`
6. `06_TRUST_REASON_AND_EXTERNAL_ADOPTION.md`
   - implementation archive: `docs/projects/archive/Proof/TRAD04182026-IMPLEMENTATION-CLOSEOUT/`

## Recommended Iteration Order

1. Trusted Run Witness Runtime
2. Control Plane As Witness Substrate
3. Mathematical Foundation And Invariants
4. Offline Verifier And Claim Ladder
5. First Useful Workflow Slice
6. Trust Reason And External Adoption

This order keeps the product claim small first, then defines the substrate, then formalizes what can be verified, then builds the external verifier and first useful workflow around that bounded claim.

## Adoption Rule

While this packet was active, any future execution move from it had to:

1. name exactly which child doc is being adopted
2. state whether adoption is full or a bounded subset
3. restate the current shipped baseline
4. define the compare scope and operator surface before implementation starts
5. say what claim tier is being targeted
6. update `docs/ROADMAP.md` in the same change if the work becomes active
7. update durable specs or `CURRENT_AUTHORITY.md` in the same change if source-of-truth behavior changes

## Completion Standard For Any Adopted Child

While this packet was active, an adopted child was not complete until it had:

1. a bounded requirements document or implementation plan
2. a proof artifact path
3. observed path recorded as `primary`, `fallback`, `degraded`, or `blocked`
4. observed result recorded as `success`, `failure`, `partial success`, or `environment blocker`
5. a truthful claim tier from `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
6. explicit remaining blockers or drift
