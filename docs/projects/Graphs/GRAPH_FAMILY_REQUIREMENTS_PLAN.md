# Graph Family Requirements Plan

Last updated: 2026-03-30
Status: Checkpoint complete / paused
Owner: Orket Core
Canonical implementation plan: `docs/projects/Graphs/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
Lane type: Graph-family checkpoint authority / paused requirements plan

Checkpoint note:
1. Checkpoint establishment is complete.
2. No active Graphs requirements-hardening slice is open.
3. Phase-scoped closeouts remain archived at:
   1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/`
   2. `docs/projects/archive/Graphs/GF03302026-APPENDIX-SYNC-CLOSEOUT/`

## Authority posture

This document is the current canonical non-archive Graphs requirements checkpoint.

It restates the bounded outcomes of the completed Graphs phase-scoped lanes without reviving those completed docs as active requirements work.

The shipped durable contract remains `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`.

## Current accepted positions

As of 2026-03-30:
1. `authority` graph remains non-normative filtered-view vocabulary over the existing semantic graph core
2. `decision` graph remains non-normative filtered-view vocabulary over the existing semantic graph core
3. `closure` graph remains non-normative family vocabulary beyond the already-shipped normative `closure_path` view token
4. `resource-authority` graph remains non-normative family vocabulary beyond the already-shipped normative `resource_authority_path` view token
5. `workload-composition` remains deferred until one stable operator question is restated against named authoritative parent-child lineage
6. `counterfactual/comparison` remains deferred until one comparison basis and truthful path-labeling rule set are fixed up front

## Archived source packets

The full phase-scoped requirements record remains in:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/CLOSEOUT.md`
3. `docs/projects/archive/Graphs/GF03302026-APPENDIX-SYNC-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
4. `docs/projects/archive/Graphs/GF03302026-APPENDIX-SYNC-CLOSEOUT/CLOSEOUT.md`

## Reopen questions

Future Graphs work should reopen only when it can answer at least one bounded question cleanly:
1. which new graph-family promotion is being requested
2. whether the requested family is still a filtered view or now needs a separate artifact family
3. what exact same-change contract, schema, registry, runtime, and proof surfaces must move together

## Same-change update rules

When this checkpoint changes materially, the same change must update:
1. `docs/projects/Graphs/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/projects/Graphs/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
3. `docs/ROADMAP.md`
4. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` only when the active contract story changes
