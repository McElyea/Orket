# SPC-05 Run Summary Closeout Implementation Plan

Last updated: 2026-03-13
Status: Active
Owner: Orket Core
Parent lane: `docs/projects/runtime-stability-closeout/IMPLEMENTATION-PLAN.md`

## 1. Decision Lock

Chosen closeout target: `implement canonical run_summary closeout`.
Explicitly excluded target(s): narrowing `run_summary.json` out of the active contract and broader observability expansion beyond canonical summary emission on top of the already-shipped run graph and schema registry.

## 2. Objective

Close SPC-05 by making `run_summary.json` a canonical emitted artifact and derivable runtime surface for every finalized run, using the already shipped run-graph and schema-registry foundations instead of narrowing the summary contract away.

## 3. In Scope

1. Canonical `run_summary.json` emission for every finalized run.
2. A single-source `generate_run_summary(run_id)` runtime surface or equivalent canonical generator reused by finalize and reconstruction paths.
3. Declared summary schema and deterministic reconstruction rules.
4. Alignment between emitted summary artifact, ledger `summary_json`, and run-graph consumption.

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
3. Emit `run_summary.json` under `runs/<session_id>/run_summary.json` for every finalized run.
4. Add a declared summary schema contract, likely `core/artifacts/run_summary_schema.json`, and keep the schema registry aligned with the emitted artifact.

### 5.2 Integration Alignment

1. Replace or subordinate `ExecutionPipeline._build_run_summary(...)` so subsystem-local helpers are no longer the authoritative summary contract.
2. Keep protocol-ledger `summary_json` content aligned with emitted `run_summary.json`.
3. Ensure run-graph generation consumes the canonical summary artifact only if that emitted contract actually exists, or otherwise leave graph reconstruction independent and truthful.
4. Keep Focus Item 5 failure semantics explicit: summary generation failure is non-fatal to the original run result and is logged as a separate error event or equivalent runtime error record.

### 5.3 Proof Hardening

1. Add a `contract` test for summary schema validation and deterministic reconstruction, likely in a new file such as `tests/runtime/test_run_summary.py`.
2. Tighten `tests/application/test_execution_pipeline_protocol_run_ledger.py` as `integration` proof for emitted summary behavior on incomplete, failed, and terminal-failure paths.
3. Tighten `tests/application/test_execution_pipeline_run_ledger.py` as `integration` proof for aligned ledger summary content on the non-protocol path.
4. Extend `tests/runtime/test_run_graph_reconstruction.py` or add a companion parity test so emitted summary content and reconstructed summary content are compared for equivalent runs.
5. Keep `tests/runtime/test_artifact_retention_tiers.py` as a `contract` guard for retention-policy alignment, and extend schema-registry validation tests if a new summary schema file is introduced.

### 5.4 Runtime Code Changes

1. Prefer a small dedicated summary module rather than spreading summary authority further across `execution_pipeline.py` and ledger adapters.
2. Likely touched runtime paths:
   1. `orket/runtime/run_summary.py` or equivalent new canonical summary module
   2. `orket/adapters/storage/async_protocol_run_ledger.py`
   3. `orket/runtime/execution_pipeline.py`
   4. `orket/adapters/storage/async_repositories.py` or `orket/adapters/storage/async_dual_write_run_ledger.py` if summary payload shape or parity handling needs alignment

## 6. Verification Plan

1. `contract`: new summary-schema and reconstruction test, likely `tests/runtime/test_run_summary.py`
2. `integration`: `tests/application/test_execution_pipeline_protocol_run_ledger.py`
3. `integration`: `tests/application/test_execution_pipeline_run_ledger.py`
4. `integration`: `tests/runtime/test_run_graph_reconstruction.py` or a dedicated summary-parity companion
5. `contract`: `tests/runtime/test_artifact_retention_tiers.py`
6. Governance: `python scripts/governance/check_docs_project_hygiene.py`

## 7. Exit Criteria

1. Every finalized run emits canonical `run_summary.json`.
2. The canonical summary generator is single-sourced and reused by finalize/reconstruction paths.
3. Emitted summary content matches reconstructed summary content for equivalent runs.
4. Summary generation failure is non-fatal to the run result and is separately recorded.
5. `run_summary.json`, `run_graph.json`, and the artifact schema registry remain aligned.
