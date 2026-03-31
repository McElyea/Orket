# Graph Family Implementation Plan

Last updated: 2026-03-30
Status: Completed (archived lane closeout authority)
Owner: Orket Core
Lane type: Graph-family requirements hardening / archived closeout authority

Requirements authority: `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`

Archive note:
1. Completed and archived on 2026-03-30.
2. Closeout authority: `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/CLOSEOUT.md`

## Authority posture

This document is the archived execution authority for the completed Graphs lane.

The archived requirements authority remains `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`.
The shipped V1 contract remains authoritative in `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`.

This plan does not reopen the archived Graph implementation lane at `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/`.
It records how the completed requirements-hardening lane closed before any new graph-family implementation request is accepted.
Any future graph-family promotion or implementation work must reopen as a new explicit roadmap lane.

## Source authorities

This plan is bounded by:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
3. `docs/ROADMAP.md`
4. `docs/ARCHITECTURE.md`
5. `CURRENT_AUTHORITY.md`
6. `docs/projects/archive/Graph/GR03302026-LANE-CLOSEOUT/CLOSEOUT.md`
7. the shipped V1 graph runtime surfaces, only as reference boundaries:
   1. `orket/runtime/run_evidence_graph.py`
   2. `orket/runtime/run_evidence_graph_projection.py`
   3. `orket/runtime/run_evidence_graph_rendering.py`
   4. `scripts/observability/emit_run_evidence_graph.py`

## Purpose

Execute the Graphs requirements-hardening lane without broadening the shipped V1 graph contract prematurely.

This plan exists to answer the requirements-lane questions in execution order:
1. which future graph families hold one clean operator question
2. which future graph families remain filtered views over the existing semantic core
3. which future graph families, if any, require a separate artifact family
4. what exact contract deltas would be needed before any later implementation lane could begin

## Decision lock

The following remain fixed while this plan executes:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` remains the authoritative shipped V1 contract
2. the current `run_evidence_graph` runtime, schema, registry, and operator path remain authoritative for the shipped family
3. this lane is requirements-hardening work, not graph-family implementation work
4. no future family may mint lineage unsupported by first-class records
5. no future family may broaden or reinterpret the shipped V1 contract without explicit same-change contract, schema, registry, roadmap, and authority updates
6. deferred families may stay deferred if the requirements case is not clean enough

## Current execution checkpoint

As of 2026-03-30:
1. Slice 1 is complete.
2. Slice 2 is complete.
3. Slice 3 is complete.
4. Slice 4 is complete.
5. Accepted operator questions, filtered-view decisions, bounded source rules, rendering-emphasis rules, and deferred reopen criteria are recorded in `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`.
6. No new durable contract promotion was accepted from this lane; the truthful handoff is explicit continued deferral.
7. `workload-composition` and `counterfactual/comparison` remain deferred and require a new explicit lane before any later promotion or implementation.
8. the shipped `run_evidence_graph` family remains unchanged, and this lane closed without runtime, schema, registry, or authority promotion work.

Lane closeout status:
1. no active next slice; the lane is archived

## Execution order

Execution order is authoritative for this lane.

### Slice 1 - Operator-question freeze

Status:
1. complete on 2026-03-30

Objective:
1. restate each in-scope future family in one clean operator-question form and reject or defer any family that cannot keep one stable question

Primary touchpoints:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`

Required deliverables:
1. one accepted operator question for `authority`, `decision`, `closure`, and `resource-authority` families
2. explicit defer-or-reject disposition for any family whose question remains ambiguous
3. explicit confirmation that the shipped `run_evidence_graph` family remains unchanged

Representative proof commands:
1. `python scripts/governance/check_docs_project_hygiene.py`

Same-change doc updates:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md` if execution order or lane state changes
3. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` only if Appendix A wording must be clarified without broadening normative V1 contract text

Slice exit condition:
1. every in-scope family has one clean operator question or an explicit defer-or-reject disposition

### Slice 2 - Semantic-core reuse versus new artifact-family decision

Status:
1. complete on 2026-03-30

Objective:
1. decide per family whether the existing semantic graph core is sufficient or whether a separate artifact family would be required later

Primary touchpoints:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
3. `CURRENT_AUTHORITY.md` only if an accepted future-family authority posture must be recorded

Required deliverables:
1. per-family decision of `filtered view` versus `new artifact family`
2. bounded rationale for each decision
3. explicit prohibition on silent family splitting

Representative proof commands:
1. `python scripts/governance/check_docs_project_hygiene.py`
2. `python -m pytest -q tests/runtime/test_run_evidence_graph_rendering.py tests/scripts/test_emit_run_evidence_graph.py`

Same-change doc updates:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` if Appendix A vocabulary or promotion boundaries change materially
3. `CURRENT_AUTHORITY.md` only if the accepted authority story changes

Slice exit condition:
1. every in-scope family has a truthful filtered-view versus new-artifact-family decision

### Slice 3 - Family requirement hardening

Status:
1. complete on 2026-03-30

Objective:
1. define bounded source rules, visible distinctions, and rendering-emphasis rules for each family admitted past Slice 2

Primary touchpoints:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`

Required deliverables:
1. bounded source and lineage rules per admitted family
2. rendering rules that preserve source-family identity and avoid invented nodes or edges
3. explicit reopen criteria for deferred workload-composition and counterfactual/comparison families

Representative proof commands:
1. `python scripts/governance/check_docs_project_hygiene.py`
2. `python -m pytest -q tests/runtime/test_run_evidence_graph_rendering.py tests/runtime/test_run_evidence_graph_projection.py`

Same-change doc updates:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` only if non-normative appendix language must be sharpened or a normative contract promotion is explicitly accepted

Slice exit condition:
1. admitted future families have bounded requirement candidates and deferred families have explicit reopen criteria

### Slice 4 - Promotion or defer handoff

Status:
1. complete on 2026-03-30

Objective:
1. close the lane with a truthful recommendation for either durable contract promotion or explicit continued deferral

Primary touchpoints:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
3. `docs/ROADMAP.md`
4. `CURRENT_AUTHORITY.md` only if promotion is accepted

Required deliverables:
1. a recommended promoted contract-delta set, if any
2. an explicit list of same-change surfaces that must move together before later implementation
3. a clear statement of what remains non-normative if promotion is not accepted

Representative proof commands:
1. `python scripts/governance/check_docs_project_hygiene.py`

Same-change doc updates:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
3. `docs/ROADMAP.md` if the lane completes, pauses, or narrows
4. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` if contract promotion is explicitly accepted
5. `CURRENT_AUTHORITY.md` only if contract promotion changes active authority posture

Slice exit condition:
1. the lane ends with either a clean promotion-ready contract delta set or an explicit defer-or-reject outcome with no hidden implementation authority

## Same-change update rules

When this lane changes state or materially sharpens accepted graph-family requirements, the same change must update:
1. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
2. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_IMPLEMENTATION_PLAN.md`
3. `docs/ROADMAP.md` when active-lane posture changes
4. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` only when accepted taxonomy or contract boundaries change materially
5. `CURRENT_AUTHORITY.md` only when active authority posture changes

Do not let the requirements authority, implementation plan, roadmap, and shipped V1 spec drift into parallel stories.

## Stop conditions

Stop and narrow scope if any of the following occurs:
1. the lane starts writing runtime implementation tasks before contract promotion is accepted
2. a family cannot hold one stable operator question
3. a proposed family needs invented lineage or hidden semantic additions to stay legible
4. Appendix A starts acting like active normative contract text without the required same-change promotions
5. roadmap, requirements authority, and implementation plan no longer tell one story

## Completion gate

This lane is complete only when:
1. each in-scope family has one operator question or an explicit defer-or-reject decision
2. each admitted family has a truthful filtered-view versus new-artifact-family decision
3. each admitted family has bounded requirement candidates for source rules and rendering rules
4. deferred families have explicit reopen criteria
5. roadmap, requirements authority, implementation plan, and shipped V1 spec tell one story
