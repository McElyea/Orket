# Orket Roadmap

This roadmap tracks only unfinished work.
Architecture authority: `docs/OrketArchitectureModel.md`.

## Current State

The prior release gate is complete:
1. `python -m pytest tests/ -q` -> 197 passed.
2. `python -m pytest --collect-only -q` -> 197 collected.
3. `rg -n "except Exception" orket` -> 0 matches.
4. Load artifact archived: `benchmarks/results/2026-02-11_phase5_load.json`.
5. CI includes `quality`, `docker_smoke`, and `migration_smoke` jobs.
6. `tools.py` decomposition baseline completed:
- Stable runtime invocation seam (`ToolRuntimeExecutor`).
- Tool strategy decision node with `process_rules` + `ORKET_TOOL_STRATEGY_NODE` override.
- Default mapping parity validated with contract/parity tests.
7. Architecture documentation published:
- `docs/ARCHITECTURE.md` now defines folder architecture and dependency direction rules.
- Decision-node override examples documented, including `tool_strategy_node` + `ORKET_TOOL_STRATEGY_NODE`.
8. FastAPI lifecycle migration completed:
- Replaced deprecated startup hook with lifespan handlers in `orket/interfaces/api.py`.
9. Release pipeline closure completed:
- CI uploads benchmark evidence artifacts (`benchmarks/results/*.json`).
- One-command release smoke script added: `python scripts/release_smoke.py`.
10. Volatility evidence archived:
- Churn report artifact: `benchmarks/results/2026-02-11_phaseH_churn.json`.
- Repro command: `python scripts/churn_report.py --scope orket --top 20`.
11. API runtime strategy seam extracted:
- Added `ApiRuntimeStrategyNode` with default implementation.
- `orket/interfaces/api.py` now resolves origins/session-id/asset-id through decision node.
- Supports `process_rules.api_runtime_node` with `ORKET_API_RUNTIME_NODE` env override.
12. Sandbox + engine runtime policy seams extracted:
- Added `SandboxPolicyNode` and `EngineRuntimePolicyNode` with default implementations.
- `orket/services/sandbox_orchestrator.py` now resolves sandbox id/compose/database policy through node.
- `orket/orchestration/engine.py` now resolves environment bootstrap and config-root policy through node.
- Supports `process_rules` selection plus env overrides:
  - `ORKET_SANDBOX_POLICY_NODE`
  - `ORKET_ENGINE_RUNTIME_NODE`
13. Loader/runtime selection seams extracted from `orket/orket.py`:
- Added `LoaderStrategyNode` and `ExecutionRuntimeStrategyNode` with default implementations.
- `ConfigLoader` now resolves path/override policy through loader strategy node.
- `ExecutionPipeline` now resolves run/build id selection through execution runtime strategy node.
- Supports `process_rules` + env overrides:
  - `ORKET_LOADER_STRATEGY_NODE`
  - `ORKET_EXECUTION_RUNTIME_NODE`
14. Tools package decomposition completed:
- Extracted stable runtime invocation to `orket/tool_runtime/runtime.py`.
- Extracted default tool-map composition to `orket/tool_strategy/default.py`.
- Preserved existing decision-node API (`DefaultToolStrategyNode`) by delegating to new module.
15. Execution pipeline wiring seam extracted:
- Added `PipelineWiringStrategyNode` with default implementation.
- `ExecutionPipeline` now delegates sandbox/webhook/bug-fix/orchestrator wiring through node.
- `run_rock` subordinate `ExecutionPipeline` spawn now delegates through node policy.
- Supports `process_rules.pipeline_wiring_node` + `ORKET_PIPELINE_WIRING_NODE`.
16. Dependency-direction gate added:
- Script: `scripts/check_dependency_direction.py`.
- CI quality job now enforces architecture dependency direction rules.
- Rules aligned with `docs/ARCHITECTURE.md`.
17. Runtime module split completed with compatibility shims:
- `ConfigLoader` moved to `orket/runtime/config_loader.py`.
- `ExecutionPipeline` + entrypoints moved to `orket/runtime/execution_pipeline.py`.
- `orket/orket.py` now re-exports legacy symbols for compatibility.
18. Decision-node override matrix smoke tests added:
- `tests/test_decision_node_override_matrix.py` verifies process-rules and env override behavior across runtime seams.
19. Sandbox command-runner seam extracted:
- Added infrastructure adapter: `orket/infrastructure/command_runner.py`.
- `SandboxOrchestrator` now delegates subprocess execution through `CommandRunner`.
- Added runner-injection test: `tests/test_sandbox_command_runner.py`.
20. Roadmap metrics drift gate added:
- Script: `scripts/check_roadmap_metrics.py`.
- CI quality job enforces roadmap pass/collect counters against live pytest output.
21. CI architecture fast-path added:
- New `architecture_gates` job runs before `quality`.
- Fast gate enforces dependency direction and quick roadmap metric validation.

## Phase N: Volatility Decomposition (Next)

Goal: keep reducing monolithic hotspots while preserving behavior parity.

1. Extract orchestration execution-loop policy seams from `orket/orchestration/orchestrator.py` into focused decision/runtime nodes.
2. Add architecture coverage tests for orchestrator seam overrides in at least one end-to-end execution scenario.

## Working Model

Use `Exists -> Working -> Done`:
1. Exists: item defined here with acceptance criteria.
2. Working: one active note in `Agents/HANDOFF.md`.
3. Done: verified and removed from roadmap with one `CHANGELOG.md` line.
