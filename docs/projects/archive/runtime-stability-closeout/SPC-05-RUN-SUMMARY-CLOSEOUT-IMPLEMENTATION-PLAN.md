# SPC-05 Run Summary Closeout Implementation Plan

Last updated: 2026-03-13
Status: Archived
Owner: Orket Core
Parent lane: `docs/projects/archive/runtime-stability-closeout/IMPLEMENTATION-PLAN.md`

Archive note: Historical slice plan preserved after the parent runtime-stability structural closeout lane completed on 2026-03-13.

## 1. Decision Lock

Chosen closeout target: `implement canonical run_summary closeout`.
Explicitly excluded target(s): narrowing `run_summary.json` out of the active contract and broader observability expansion beyond canonical summary emission on top of the already-shipped run graph and schema registry.

## 2. Objective

Close SPC-05 by making `run_summary.json` a canonical emitted artifact and derivable runtime surface for every finalized run, using the already shipped run-graph and schema-registry foundations instead of narrowing the summary contract away.

## 3. In Scope

1. Canonical `run_summary.json` emission for every finalized run.
2. A single-source `generate_run_summary(run_id)` runtime surface or equivalent canonical generator reused by finalize and reconstruction paths.
3. Declared summary schema and deterministic reconstruction rules.
4. A single unambiguous artifact identity rule: `run_summary.json` is run-scoped, keyed by canonical `run_id`, and emitted under `runs/<run_id>/run_summary.json`.
5. Alignment between emitted summary artifact, ledger `summary_json`, and run-graph consumption.

## 4. Explicitly Out Of Scope

1. Removing `run_summary.json` from the active closeout contract.
2. Replacing or broadening the already shipped `run_graph.json` and artifact schema registry contracts.
3. New dashboard, heatmap, or telemetry product work beyond the summary artifact itself.

## 5. Planned Changes

### 5.1 Canonical Summary Contract Completion

1. Add a canonical runtime summary generator, preferably in a dedicated module such as `orket/runtime/run_summary.py`, and route protocol finalize through that single source.
2. Expand the canonical summary payload so it satisfies Focus Item 5:
   1. `run_id`
   2. `status`
   3. `duration_ms`
   4. `tools_used`
   5. `artifact_ids`
   6. `failure_reason`
3. Lock artifact identity explicitly: `generate_run_summary(run_id)` and the emitted artifact refer to the same run-scoped object, and the canonical path is `runs/<run_id>/run_summary.json`.
4. Emit `run_summary.json` for every finalized run. If full summary derivation fails, emit a degraded-but-valid fallback summary artifact for that same `run_id` instead of omitting the artifact.
5. Add a declared summary schema contract, likely `core/artifacts/run_summary_schema.json`, and keep the schema registry aligned with the emitted artifact.
6. Lock schema semantics explicitly:
   1. `status` must reuse the canonical runtime status vocabulary already enforced by the run ledger; do not introduce a summary-only enum.
   2. `failure_reason` must be `null` when the finalized run carries no failure reason and must equal the canonical finalized failure reason when one exists.
   3. `tools_used` and `artifact_ids` must use deterministic empty-array semantics when none are present.
   4. `duration_ms` must be a non-negative integer when derivable and may be `null` only in the degraded fallback artifact when duration cannot be reconstructed from canonical inputs.

### 5.2 Integration Alignment

1. Replace or subordinate `ExecutionPipeline._build_run_summary(...)` so subsystem-local helpers are no longer the authoritative summary contract.
2. Keep protocol-ledger `summary_json` content aligned with emitted `run_summary.json`.
3. Lock run-graph independence explicitly: `run_graph.json` must remain independently reconstructible from canonical ledger/artifact state, may share derivation inputs or helper logic with `run_summary`, and must not depend on the presence of an emitted `run_summary.json` file.
4. Keep Focus Item 5 failure semantics explicit: summary generation failure is non-fatal to the original run result, emits the degraded fallback summary artifact for the same `run_id`, and is logged as a separate error event or equivalent runtime error record.

### 5.3 Proof Hardening

1. Add a `contract` test for summary schema validation and deterministic reconstruction, likely in a new file such as `tests/runtime/test_run_summary.py`.
2. Add a `contract` or `integration` proof that forced summary-derivation failure still emits the degraded fallback summary artifact and separately records the summary-generation error.
3. Tighten `tests/application/test_execution_pipeline_protocol_run_ledger.py` as `integration` proof for emitted summary behavior on incomplete, failed, and terminal-failure paths.
4. Tighten `tests/application/test_execution_pipeline_run_ledger.py` as `integration` proof for aligned ledger summary content on the non-protocol path.
5. Extend `tests/runtime/test_run_graph_reconstruction.py` or add a companion parity test so emitted summary content and reconstructed summary content are compared for equivalent runs without introducing run-graph dependence on the emitted summary file.
6. Keep `tests/runtime/test_artifact_retention_tiers.py` as a `contract` guard for retention-policy alignment, and extend schema-registry validation tests if a new summary schema file is introduced.

### 5.4 Runtime Code Changes

1. Prefer a small dedicated summary module rather than spreading summary authority further across `execution_pipeline.py` and ledger adapters.
2. Likely touched runtime paths:
   1. `orket/runtime/run_summary.py` or equivalent new canonical summary module
   2. `orket/adapters/storage/async_protocol_run_ledger.py`
   3. `orket/runtime/execution_pipeline.py`
   4. `orket/adapters/storage/async_repositories.py` or `orket/adapters/storage/async_dual_write_run_ledger.py` if summary payload shape or parity handling needs alignment

## 6. Verification Plan

1. `contract`: new summary-schema and reconstruction test, likely `tests/runtime/test_run_summary.py`
2. `integration`: forced summary-generation-failure proof with degraded fallback artifact emission
3. `integration`: `tests/application/test_execution_pipeline_protocol_run_ledger.py`
4. `integration`: `tests/application/test_execution_pipeline_run_ledger.py`
5. `integration`: `tests/runtime/test_run_graph_reconstruction.py` or a dedicated summary-parity companion
6. `contract`: `tests/runtime/test_artifact_retention_tiers.py`
7. Governance: `python scripts/governance/check_docs_project_hygiene.py`

## 7. Exit Criteria

1. Every finalized run emits canonical `run_summary.json`, including degraded-but-valid fallback emission when full summary derivation fails.
2. The canonical summary generator is single-sourced and reused by finalize/reconstruction paths.
3. Emitted summary content matches reconstructed summary content for equivalent runs, including reproduction of the same degraded fallback form when canonical inputs are insufficient.
4. Summary generation failure is non-fatal to the run result, separately recorded, and does not prevent fallback summary emission for the same `run_id`.
5. `run_summary.json`, `run_graph.json`, and the artifact schema registry remain aligned.
