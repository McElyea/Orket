# Run Evidence Graph Implementation Plan

Last updated: 2026-03-30
Status: Archived implementation plan
Owner: Orket Core
Lane type: Additive observability artifact / archived implementation plan

## Authority posture

This document is the archived implementation plan for the completed Graph lane.

The active durable contract authority is `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`.

## Source authorities

This plan is bounded by:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `docs/ROADMAP.md`
3. `docs/ARCHITECTURE.md`
4. `CURRENT_AUTHORITY.md`
5. `core/artifacts/run_graph_schema.json`
6. `core/artifacts/schema_registry.yaml`
7. `orket/runtime/run_graph_reconstruction.py`
8. `orket/runtime/run_summary.py`
9. `orket/runtime/run_summary_control_plane.py`
10. `orket/runtime/run_ledger_projection.py`
11. `orket/adapters/storage/async_control_plane_record_repository.py`
12. `orket/adapters/storage/async_control_plane_execution_repository.py`
13. `orket/application/services/sandbox_lifecycle_view_service.py`
14. `orket/application/services/kernel_action_control_plane_view_service.py`
15. `orket/orchestration/approval_control_plane_read_model.py`
16. `orket/runtime_paths.py`

## Purpose

Implement V1 run-evidence graph emission for selected V1-covered runs without changing the existing `run_graph.json` contract.

The implementation goal is one separate semantic graph family under `runs/<session_id>/` that:
1. consumes coherent first-class run lineage for V1-covered runs
2. uses supplemental sources only for bounded annotation and ordering detail
3. fails closed when a selected run is not V1-covered or when lineage is contradictory
4. renders the same semantic truth through JSON plus human-facing views

## Decision lock

The following remain fixed while this plan executes:
1. existing `run_graph.json` stays the protocol/tool/artifact reconstruction graph
2. existing `/runs/{session_id}/execution-graph` surfaces remain execution-graph surfaces and are not repurposed for run-evidence output in V1
3. the canonical V1 artifact family is `runs/<session_id>/run_evidence_graph.json`, `run_evidence_graph.mmd`, and one rendered `run_evidence_graph.svg` or `run_evidence_graph.html`
4. the canonical V1 operator path is one script-owned command surface, not an overloaded legacy graph route
5. a run that is not V1-covered is `blocked`, not `degraded`
6. supplemental projections may annotate or order primary lineage, but may not create lineage that first-class records do not support
7. V1 must not invent a second run root

## Canonical operator path

V1 should ship one canonical operator path first:
1. `python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>`

Optional flags may add workspace-root or output-root override behavior only when that behavior preserves the canonical `runs/<session_id>/` output family for normal operation.

Do not add API or UI wrappers until the script path, schema, and proof surfaces are stable.

## Execution order

Execution order is authoritative for this lane.

### Slice 1 - Contract and schema separation

Objective:
1. land a separate semantic contract for `run_evidence_graph.json` without changing the existing `run_graph.json` contract

Primary touchpoints:
1. `core/artifacts/run_evidence_graph_schema.json`
2. `core/artifacts/schema_registry.yaml`
3. new runtime contract module under `orket/runtime/` for run-evidence graph validation and artifact writing
4. new contract tests under `tests/contracts/` and runtime tests under `tests/runtime/`

Required deliverables:
1. schema version `1.0` for `run_evidence_graph.json`
2. explicit required top-level framing for result classification, projection framing, node ids, edge ids, and source summaries
3. separate validation logic that does not share the existing `run_graph.json` node or edge vocabulary
4. blocked-artifact-shell contract for non-covered or invalid runs

Representative proof commands:
1. `python -m pytest -q tests/contracts/test_run_evidence_graph_contract.py`
2. `python -m pytest -q tests/runtime/test_run_evidence_graph_contract.py`

Same-change doc updates:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `core/artifacts/run_evidence_graph_schema.json`
3. `core/artifacts/schema_registry.yaml`

Slice exit condition:
1. `run_evidence_graph.json` has a separate schema-pinned contract, separate registry entry, and a blocked-artifact-shell contract without changing the existing `run_graph.json` vocabulary.

### Slice 2 - Primary lineage projector

Objective:
1. build one canonical semantic graph projector that consumes coherent first-class run lineage and fails closed when that lineage is missing or contradictory

Primary touchpoints:
1. new runtime projector module under `orket/runtime/` such as `run_evidence_graph.py` or a split projector/validator pair
2. `orket/adapters/storage/async_control_plane_record_repository.py`
3. `orket/adapters/storage/async_control_plane_execution_repository.py`
4. `orket/runtime_paths.py`

Required deliverables:
1. explicit V1-covered run gate using first-class `RunRecord` lineage
2. deterministic node and edge id strategy for the required primary node families
3. blocked classification when parent lineage is absent or contradictory
4. no dependence on the presence of emitted `run_summary.json` or the existing emitted `run_graph.json`

Representative proof commands:
1. `python -m pytest -q tests/runtime/test_run_evidence_graph_projection.py`
2. `python -m pytest -q tests/contracts/test_run_evidence_graph_projection_validation.py`

Same-change doc updates:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` if the covered-run gate, node families, edge families, or blocked rules change materially
2. `CURRENT_AUTHORITY.md` only if the canonical operator path or active artifact family changes authority posture

Slice exit condition:
1. the projector accepts only V1-covered runs, derives primary lineage from coherent first-class `RunRecord` lineage, and blocks rather than degrading when required parent lineage is absent or contradictory.

### Slice 3 - Supplemental annotation and bounded observation support

Objective:
1. add bounded supplemental annotation, ordering detail, and observation-node support without allowing supplemental surfaces to mint lineage

Primary touchpoints:
1. the new run-evidence graph projector module or companion source-builder module
2. `orket/runtime/run_summary.py`
3. `orket/runtime/run_summary_control_plane.py`
4. `orket/runtime/run_ledger_projection.py`
5. `orket/application/services/sandbox_lifecycle_view_service.py`
6. `orket/application/services/kernel_action_control_plane_view_service.py`
7. `orket/orchestration/approval_control_plane_read_model.py`

Required deliverables:
1. explicit source tagging for every supplemental annotation path
2. bounded `observation` node emission only from already-validated observation-linked sources
3. deterministic ordering annotation when runtime events align with primary lineage
4. blocked classification when a requested view would require invented lineage or an unavailable distinction

Representative proof commands:
1. `python -m pytest -q tests/runtime/test_run_evidence_graph_projection_validation.py`
2. `python -m pytest -q tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_run_summary_projection_consumers.py`
3. `python -m pytest -q tests/application/test_kernel_action_control_plane_view_service.py tests/integration/test_sandbox_lifecycle_view_service.py`

Same-change doc updates:
1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` if supplemental-source bounds, observation-node rules, or blocked-versus-degraded rules change materially

Slice exit condition:
1. supplemental sources contribute only bounded annotation, ordering, or observation detail, and no supplemental surface can mint lineage that first-class records do not support.

### Slice 4 - Renderers and filtered views

Objective:
1. emit deterministic semantic JSON plus Mermaid and one rendered human-view output for the required V1 views

Primary touchpoints:
1. the new run-evidence graph runtime module
2. a new rendering module under `orket/runtime/` for Mermaid and HTML or SVG emission
3. `scripts/observability/emit_run_evidence_graph.py`

Required deliverables:
1. `full lineage`, `failure path`, `resource authority path`, and `closure path` views derived from one semantic graph JSON
2. canonical output under `runs/<session_id>/`
3. a rendered output path that does not change semantic meaning at layout time
4. no change to the existing execution-graph API route in V1

Representative proof commands:
1. `python -m pytest -q tests/runtime/test_run_evidence_graph_rendering.py`
2. `python -m pytest -q tests/scripts/test_emit_run_evidence_graph.py`

Same-change doc updates:
1. `CURRENT_AUTHORITY.md` only when the script path or output family becomes active authority

Slice exit condition:
1. full-lineage, failure-path, resource-authority, and closure-path views all derive from one semantic graph JSON under `runs/<session_id>/` without changing semantic meaning at render time.

### Slice 5 - Integration proof and authority sync

Objective:
1. prove the new artifact family on covered runs and update the active authority story in the same changes that make the lane real

Primary touchpoints:
1. `CURRENT_AUTHORITY.md`
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
3. `docs/ROADMAP.md`
4. `core/artifacts/run_evidence_graph_schema.json`
5. `core/artifacts/schema_registry.yaml`
6. the new runtime and script surfaces from Slices 1 through 4

Required deliverables:
1. structural proof that the new artifact family is separate from the existing `run_graph.json` contract
2. integration proof on covered runs with success, recovery, reservation or lease lineage, and blocked or reconciliation closure
3. real-path script execution against at least one covered run id
4. same-change authority sync once the canonical operator path becomes active

Representative proof commands:
1. `python -m pytest -q tests/contracts/test_run_evidence_graph_contract.py tests/runtime/test_run_evidence_graph_projection.py tests/runtime/test_run_evidence_graph_rendering.py tests/scripts/test_emit_run_evidence_graph.py`
2. `python -m pytest -q tests/integration/test_sandbox_lifecycle_view_service.py tests/application/test_kernel_action_control_plane_view_service.py`
3. `ORKET_DISABLE_SANDBOX=1 python scripts/observability/emit_run_evidence_graph.py --run-id <covered_run_id>`

Same-change doc updates:
1. `docs/ROADMAP.md`, including the Graph row in the Project Index
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
3. `CURRENT_AUTHORITY.md`
4. `core/artifacts/run_evidence_graph_schema.json`
5. `core/artifacts/schema_registry.yaml`

Slice exit condition:
1. structural and integration proof are green, the canonical script path works on at least one covered run id, and roadmap, requirements, schema, registry, and authority docs tell one story.

## Same-change update rules

When execution lands or materially changes the active contract, the same change must update:
1. `docs/ROADMAP.md`, including the Graph row in the Project Index
2. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
3. `core/artifacts/run_evidence_graph_schema.json`
4. `core/artifacts/schema_registry.yaml`
5. `CURRENT_AUTHORITY.md` once the canonical operator path or artifact family becomes active authority

Do not let runtime code, schema, registry, roadmap, and authority docs drift into parallel stories.

## Stop conditions

Stop and narrow scope if any of the following occurs:
1. the implementation starts broadening the existing `run_graph.json` contract instead of shipping a separate `run_evidence_graph.json` family
2. the plan drifts toward repurposing `/runs/{session_id}/execution-graph` instead of keeping one separate operator path
3. a selected view depends on invented lineage or free-text log inference to remain legible
4. the intended covered run set cannot truthfully satisfy coherent first-class `RunRecord` lineage
5. rendering choices start adding semantic meaning that is not present in the semantic graph JSON

## Completion gate

This lane is complete only when:
1. `run_evidence_graph.json` is schema-pinned and registry-pinned separately from `run_graph.json`
2. a V1-covered run can emit the canonical artifact family under `runs/<session_id>/`
3. a non-V1-covered run produces `blocked`, not `degraded`
4. required node and edge families are derived from bounded primary and supplemental sources exactly as defined in the requirements
5. full-lineage, failure-path, resource-authority, and closure-path views all derive from the same semantic graph JSON
6. structural and integration proof are green
7. the active roadmap, project index, requirements, schema, registry, and authority docs tell one story
