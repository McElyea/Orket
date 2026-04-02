# Graphs Authority And Decision Views Reopen Implementation Plan
Last updated: 2026-04-01
Status: Completed archived implementation authority
Owner: Orket Core
Lane type: Graphs / authority and decision views reopen

Paired requirements authority:
1. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_REQUIREMENTS.md`

Closeout authority:
1. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/CLOSEOUT.md`

Historical authorities:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/CLOSEOUT.md`
3. `docs/projects/archive/Graphs/GF03312026-CHECKPOINT-CLOSEOUT/CLOSEOUT.md`
4. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Authority posture

This document is the archived implementation authority for the completed `conditional Graphs reopen for authority and decision views only` lane formerly recorded in `docs/ROADMAP.md`.

The paired requirements companion remains `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_REQUIREMENTS.md`.
This lane is bounded to one exact reopen family centered on operator-facing `authority` and `decision` filtered views over the existing `run_evidence_graph` semantic core.

## Source authorities

This plan is bounded by:
1. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_REQUIREMENTS.md`
2. `docs/ROADMAP.md`
3. `docs/ARCHITECTURE.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
6. `docs/projects/archive/Graphs/GF03302026-LANE-CLOSEOUT/CLOSEOUT.md`
7. `docs/projects/archive/Graphs/GF03312026-CHECKPOINT-CLOSEOUT/CLOSEOUT.md`
8. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Purpose

Execute the narrowest explicit Graphs reopen worth doing now: decide whether `authority` and `decision` can become operator-facing filtered views without changing the canonical graph family, operator path, or authority posture.

This lane exists to deliver:
1. one selected `authority` plus `decision` reopen family
2. one explicit source and rendering story for those views
3. one bounded implementation path that keeps `run_evidence_graph` as the only graph artifact family
4. one truthful proof set for the touched graph surfaces

## Selected bounded scope

This lane is limited to:
1. `core/artifacts/run_evidence_graph_schema.json`
2. `core/artifacts/schema_registry.yaml` only if same-change registration updates are required
3. `orket/runtime/run_evidence_graph.py`
4. `orket/runtime/run_evidence_graph_projection_support.py`
5. `orket/runtime/run_evidence_graph_projection.py`
6. `orket/runtime/run_evidence_graph_rendering.py`
7. `scripts/observability/emit_run_evidence_graph.py`
8. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
9. `CURRENT_AUTHORITY.md`
10. `docs/RUNBOOK.md` only if operator command or interpretation text changes
11. directly tied proof files only

## Non-goals

This lane does not:
1. create a new graph JSON family, schema family, or operator command separate from `run_evidence_graph`
2. reopen `workload-composition`, `counterfactual/comparison`, or generic visualization work
3. broaden into UI or analytics product work
4. revisit unrelated Graphs archive history except where the promoted family must stay truthful

## Current truthful starting point

The current implementation baseline is:
1. `run_evidence_graph` V1 is already shipped and authoritative
2. the runtime and script currently admit `full_lineage`, `failure_path`, `resource_authority_path`, and `closure_path`
3. `authority` and `decision` remain archived filtered-view vocabulary rather than active runtime view tokens
4. any new Graphs work had to reopen as a new explicit roadmap lane, and this lane is that reopen

## Current proof baseline

Current proof entrypoints around the selected graph-view family include:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_evidence_graph_runtime_contract.py`
2. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_evidence_graph_projection.py`
3. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_evidence_graph_rendering.py`
4. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_emit_run_evidence_graph.py`
5. `python scripts/governance/check_docs_project_hygiene.py`

## Execution plan

### Step 1 - Lock the selected reopen family

Deliver:
1. one exact statement that this reopen is limited to `authority` and `decision`
2. one exact mapping of those views to the existing `run_evidence_graph` semantic core
3. one explicit list of what remains out of scope and deferred

### Step 2 - Promote only if the semantic core is sufficient

Deliver:
1. one bounded decision on how `authority` and `decision` are surfaced inside the existing graph family
2. one implementation that reuses existing node, edge, and lineage families instead of minting new primary graph nouns
3. one fail-closed behavior when the selected view family cannot be projected truthfully

### Step 3 - Align operator path and docs

Deliver:
1. one canonical operator path for the selected view family through the existing graph-emission command
2. one same-change contract and authority-doc sync for any admitted view-token or rendering change
3. one truthful operator interpretation story in touched docs only

### Step 4 - Prove and close

Deliver:
1. one proof set for projection, rendering, and script behavior covering the selected view family
2. one docs hygiene pass for the promoted Graphs lane structure
3. one lane closeout only if the selected reopen goals are fully satisfied

## Same-change update targets

If this lane changes materially, the same change must update:
1. `docs/ROADMAP.md`
2. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_REQUIREMENTS.md`
3. `docs/projects/archive/Graphs/GF04012026-AUTHORITY-DECISION-VIEWS-REOPEN-CLOSEOUT/GRAPH_AUTHORITY_DECISION_VIEWS_REOPEN_IMPLEMENTATION_PLAN.md`
4. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md` when this promoted candidate changes state
5. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` if admitted view tokens, rendering posture, or operator interpretation changes
6. `CURRENT_AUTHORITY.md` and `docs/RUNBOOK.md` when canonical graph operator commands or surfaced view posture changes

## Lane completion gate

This lane is complete only when:
1. the selected `authority` and `decision` reopen family is the only selected Graphs family
2. the canonical `run_evidence_graph` artifact family remains the only admitted graph artifact family
3. one operator path and one truthful source/rendering story exist for each selected view
4. proof exists for the touched graph surface family
5. same-change authority docs remain aligned

## Stop conditions

Stop and narrow scope if:
1. the work starts widening beyond `authority` and `decision`
2. the implementation needs a second graph artifact family or a second operator path
3. proof starts depending on unrelated runtime redesign or broader Graphs platform work
4. the reopen cannot improve operator truth without a broader refactor than this lane admits
