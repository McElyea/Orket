# Graphs Authority And Decision Views Reopen Requirements
Last updated: 2026-04-01
Status: Completed archived requirements companion
Owner: Orket Core
Lane type: Graphs / authority and decision views reopen requirements

Paired implementation authority:
1. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_IMPLEMENTATION_PLAN.md`

Closeout authority:
1. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/CLOSEOUT.md`

Historical authorities:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/GRAPH_FAMILY_REQUIREMENTS_PLAN.md`
3. `docs/projects/archive/Graphs/GF03312026-CHECKPOINT-CLOSEOUT/CLOSEOUT.md`
4. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Authority posture

This document is the archived scoped requirements companion for the completed Graphs `conditional Graphs reopen for authority and decision views only` lane formerly recorded in `docs/ROADMAP.md`.

It narrows the reopen to one exact filtered-view family over the existing `run_evidence_graph` semantic core.
It does not, by itself, authorize a second graph artifact family, a broad graph-platform reopen, workload-composition graphing, or counterfactual/comparison graph work.

## Source authorities

This requirements companion is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
5. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/CLOSEOUT.md`
6. `docs/projects/archive/Graphs/GF03312026-CHECKPOINT-CLOSEOUT/CLOSEOUT.md`
7. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Purpose

Reopen Graphs only far enough to decide whether operator-facing `authority` and `decision` views can become bounded, truthful filtered views over the already-shipped `run_evidence_graph` semantic core.

This lane exists to answer:
1. whether `authority` and `decision` can become admitted view tokens or operator-visible filtered views without creating a new artifact family
2. which existing node, edge, and lineage families are sufficient to support those views truthfully
3. which runtime, schema, rendering, and operator surfaces must change together if those views are promoted
4. what proof is required so view promotion does not become speculative graph wording

## Selected bounded scope

This lane is limited to:
1. the exact runtime and schema surfaces that own the shipped `run_evidence_graph` family:
   - `core/artifacts/run_evidence_graph_schema.json`
   - `core/artifacts/schema_registry.yaml` only if same-change schema registration updates are required
   - `orket/runtime/run_evidence_graph.py`
   - `orket/runtime/run_evidence_graph_projection_support.py`
   - `orket/runtime/run_evidence_graph_projection.py`
   - `orket/runtime/run_evidence_graph_rendering.py`
   - `scripts/observability/emit_run_evidence_graph.py`
2. the exact high-signal authority and operator docs for that surface family:
   - `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
   - `CURRENT_AUTHORITY.md`
   - `docs/RUNBOOK.md` only if operator command or interpretation text changes
3. the directly tied proof surfaces:
   - `tests/runtime/test_run_evidence_graph_runtime_contract.py`
   - `tests/runtime/test_run_evidence_graph_projection.py`
   - `tests/runtime/test_run_evidence_graph_rendering.py`
   - `tests/scripts/test_emit_run_evidence_graph.py`
4. `docs/ROADMAP.md` and this paired lane authority set
5. promotion of `authority` and `decision` filtered views only if they can remain projections over existing durable truth

## Non-goals

This lane does not:
1. create a new graph JSON artifact family separate from `run_evidence_graph`
2. reopen `workload-composition`, `counterfactual/comparison`, or generic dashboard graph work
3. broaden into UI, analytics, or portfolio visualization work
4. rewrite the shipped `full_lineage`, `failure_path`, `resource_authority_path`, or `closure_path` families except where same-change truth requires alignment
5. invent lineage or decision semantics unsupported by existing records and validated projections

## Decision lock

The following remain fixed while this lane is active:
1. `run_evidence_graph` remains the canonical additive graph artifact family and operator path
2. any `authority` or `decision` promotion must stay a filtered view over the existing semantic graph core, not a second artifact family
3. graphs remain projections and never become primary execution authority
4. `closure_path` and `resource_authority_path` remain the only currently shipped normative non-default filtered views unless this lane truthfully promotes more
5. if the reopen requires new primary record families or broader graph-platform redesign, it is out of scope for this lane

## Current truthful starting point

The current surface baseline is:
1. `run_evidence_graph` V1 is already shipped with canonical operator path `python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>`
2. the shipped selected view family is currently `full_lineage`, `failure_path`, `resource_authority_path`, and `closure_path`
3. archived Graphs lane authority froze `authority` and `decision` as non-normative filtered-view vocabulary rather than promoted runtime views
4. the archived Graphs checkpoint requires any future graph-family work to reopen as a new explicit roadmap lane

## Requirements

### GADV-01. One selected filtered-view family

The lane must stay bounded to one exact filtered-view family consisting of `authority` and `decision` views only.

That selection must name:
1. the runtime, schema, and operator surfaces in scope
2. the exact graph families and lineage sources those views may emphasize
3. the boundary beyond which the lane will not widen

### GADV-02. No second artifact family

The lane must define how `authority` and `decision` remain part of the canonical `run_evidence_graph` family if promoted.

That definition must describe:
1. whether the admitted form is one or more selected view tokens, filtered views, or equivalent bounded framing inside the existing artifact family
2. how operator commands continue to flow through the existing canonical graph-emission path
3. how the lane avoids schema, output-path, or authority duplication

### GADV-03. Explicit operator questions and lineage rules

The lane must define one operator question and one truthful lineage story for each selected view.

That definition must describe:
1. what `authority` is allowed to emphasize
2. what `decision` is allowed to emphasize
3. which node and edge families are required, optional, suppressed, or forbidden for each selected view
4. how the underlying semantic family remains visible rather than being replaced by invented graph nouns

### GADV-04. Behavioral and surface proof

The lane must name proof expectations for the touched graph-view family.

At minimum the proof set must cover:
1. projection and rendering behavior for any promoted view tokens or filtered views
2. canonical script behavior for the selected operator path
3. doc-structure hygiene for the promoted Graphs lane and touched project structure

### GADV-05. Same-change update targets

If this lane changes materially, the same change must update:
1. `docs/ROADMAP.md`
2. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_REQUIREMENTS.md`
3. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_IMPLEMENTATION_PLAN.md`
4. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md` when this promoted candidate changes state
5. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` if admitted view tokens, rendering posture, or operator interpretation changes
6. `CURRENT_AUTHORITY.md` and `docs/RUNBOOK.md` when canonical graph operator commands or surfaced view posture changes

## Requirements completion gate

This requirements companion is complete only when:
1. one exact `authority` plus `decision` filtered-view family is selected truthfully
2. the no-second-artifact-family rule is explicit
3. operator questions, lineage rules, and proof expectations are explicit
4. same-change update targets remain aligned

## Stop conditions

Stop and narrow scope if:
1. the lane starts reading like a generic Graphs reopen
2. the work depends on new durable record families or broader convergence work
3. promotion would require a second graph artifact family or a second operator path
4. proof cannot stay focused on `run_evidence_graph` plus the selected `authority` and `decision` views
