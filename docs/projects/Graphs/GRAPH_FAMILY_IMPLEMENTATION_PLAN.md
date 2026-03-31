# Graph Family Implementation Plan

Last updated: 2026-03-30
Status: Checkpoint complete / paused
Owner: Orket Core
Lane type: Graph-family checkpoint authority / paused implementation plan

Requirements authority: `docs/projects/Graphs/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`

Checkpoint note:
1. Checkpoint establishment is complete.
2. No active Graphs execution slice is open.
3. Phase-scoped closeouts remain archived at:
   1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/`
   2. `docs/projects/archive/Graphs/GF03302026-APPENDIX-SYNC-CLOSEOUT/`

## Authority posture

This document is the current canonical non-archive Graphs checkpoint authority.

It exists so future graph-family reopen work has one stable path under `docs/projects/Graphs/` without reviving completed phase-scoped docs as active execution lanes.

This document is not a completed lane record and not an active implementation slice.
The shipped durable contract remains `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`.

## Source authorities

This checkpoint is bounded by:
1. `docs/projects/Graphs/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
3. `docs/ROADMAP.md`
4. `docs/ARCHITECTURE.md`
5. `CURRENT_AUTHORITY.md`
6. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
7. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
8. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/CLOSEOUT.md`
9. `docs/projects/archive/Graphs/GF03302026-APPENDIX-SYNC-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
10. `docs/projects/archive/Graphs/GF03302026-APPENDIX-SYNC-CLOSEOUT/CLOSEOUT.md`

## Purpose

Keep one truthful current Graphs checkpoint that records:
1. what the completed Graphs phase-scoped lanes established
2. what remains deferred
3. what must happen before any future graph-family implementation lane can begin

## Current checkpoint

As of 2026-03-30:
1. the original Graphs requirements-hardening lane is complete and archived
2. the narrow Appendix A authority-sync follow-up packet is complete and archived
3. `authority`, `decision`, `closure`, and `resource-authority` remain non-normative graph-family vocabulary over the existing semantic core, except where shipped V1 already names `closure_path` and `resource_authority_path` as normative view tokens
4. `workload-composition` and `counterfactual/comparison` remain deferred
5. no runtime, schema, registry, or operator-path graph-family implementation work is currently active
6. any future graph-family promotion or implementation work must reopen explicitly from this checkpoint

## Reopen triggers

Reopen Graphs from this checkpoint only when at least one of the following is true:
1. a new explicit graph-family promotion or implementation request is accepted
2. active `run_evidence_graph` contract or roadmap docs require same-change graph-family authority sync
3. proof or authority drift is found in the active graph-family story that cannot be resolved inside the archived closeout packets alone

## Reopen expectations

If Graphs reopens from this checkpoint:
1. `docs/ROADMAP.md` must move Graphs into an active or otherwise truthful lane posture in the same change
2. new phase-scoped execution work should be recorded under `docs/projects/Graphs/` and later archived on closeout
3. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`, schema, registry, runtime, tests, and authority docs must move together when any durable contract promotion is accepted
4. future Graphs work must not treat archived phase-scoped closeout docs as active implementation authority

## Same-change update rules

When this checkpoint changes materially, the same change must update:
1. `docs/projects/Graphs/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/projects/Graphs/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
3. `docs/ROADMAP.md`
4. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` only when active contract posture changes
5. `CURRENT_AUTHORITY.md` only when active authority posture changes

## Completion posture

This checkpoint is complete as the current non-archive Graphs authority path.
It remains current until a future Graphs phase reopens and later closes into a new archive packet.
