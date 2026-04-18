# Control Plane As Witness Substrate Requirements Plan

Last updated: 2026-04-18
Status: Archived accepted requirements lane
Owner: Orket Core

Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/02_CONTROL_PLANE_AS_WITNESS_SUBSTRATE.md`
Canonical requirements draft archive: `docs/projects/archive/Proof/CPWS04182026-IMPLEMENTATION-CLOSEOUT/CONTROL_PLANE_AS_WITNESS_SUBSTRATE_REQUIREMENTS.md`
Completed dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Completed dependency: `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`

## Purpose

Promote only the `Control Plane As Witness Substrate` idea into an active requirements lane.

This lane defines how Orket should use the existing control plane as proof substrate for trusted-run witness bundles without reopening broad ControlPlane convergence work.

The first bounded rule is:

```text
No new authority noun without a verifier question it answers.
```

## Current Baseline

The lane starts from shipped or active authority:

1. target runtime architecture in `docs/ARCHITECTURE.md`
2. current authority snapshot in `CURRENT_AUTHORITY.md`
3. governed start-path matrix in `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`
4. minimum auditable record rules in `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
5. trusted-run witness contract in `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
6. trusted-run invariant contract in `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
7. ProductFlow witness proof scripts under `scripts/proof/`

## Scope

In scope:

1. define which control-plane record families are required, optional, or forbidden substitutes for trusted-run witness bundles
2. map each required family to verifier questions and failure semantics
3. identify where ProductFlow Trusted Run Witness already has enough substrate evidence
4. identify where stronger substrate evidence would reduce false-success risk
5. preserve the distinction between authority records, witness bundles, projections, reports, and human summaries
6. produce implementation handoff only after requirements are accepted

Out of scope:

1. reopening the archived ControlPlane project
2. repo-wide control-plane convergence
3. making every runtime path governed
4. adding record families without a selected verifier question
5. treating read models, review packages, packet blocks, or graphs as co-equal authority
6. changing Trusted Run Witness implementation during requirements work

## Work Items

1. Requirements hardening
   - refine the witness-substrate boundary
   - state which current control-plane records are durable authority for this lane
   - define where projections are allowed and where they are forbidden

2. Record-family matrix
   - classify required, optional, and forbidden substitutes for the first trusted-run slice
   - map each family to one or more verifier questions
   - define fail-closed behavior for missing or contradictory evidence

3. Projection discipline
   - define source-ref preservation rules for summaries and review packages
   - require projection-only framing where applicable
   - define missing-evidence markers for projections

4. Proof obligation mapping
   - map current ProductFlow witness evidence to the record-family matrix
   - name missing substrate evidence as blockers rather than implied correctness
   - avoid duplicating `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`

5. Durable spec decision
   - decide whether accepted output becomes a new spec or an appendix to an existing trusted-run spec
   - update `CURRENT_AUTHORITY.md` only if behavior, canonical paths, or source-of-truth contracts change

## Requirements Completion State

The requirements draft now includes:

1. a record-family classification vocabulary
2. an accepted first-slice record-family matrix
3. verifier-question mapping for each required family
4. projection discipline rules
5. forbidden substitute rules
6. fail-closed semantics
7. explicit missing-substrate blockers
8. ProductFlow current-coverage mapping
9. durable spec extraction decision
10. remaining implementation decisions

The lane remains active because requirements closeout requires user acceptance or explicit retirement.

## Completion Gate

This requirements lane can close only when:

1. the accepted record-family matrix names required, optional, and forbidden substitute evidence
2. every required record family has an explicit verifier question
3. every missing or contradictory record condition has fail-closed semantics
4. projection-only evidence cannot replace authority records
5. remaining implementation decisions are listed explicitly
6. the user accepts the requirements or explicitly retires the lane

## Resolved Decisions

1. ProductFlow `authority_lineage` fields are first-slice witness evidence over durable authority or authority-preserving projections; run summary, review package, graph, and Packet blocks remain projection-only.
2. Current ProductFlow verifier success does not require workload/catalog evidence, a full serialized attempt record, or a full serialized lease record.
3. Accepted output should be extracted as a standalone `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md` contract before implementation.
4. The first implementation should consume the matrix through Trusted Run Witness verifier tests and optional verifier output, not through broad ControlPlane expansion.
