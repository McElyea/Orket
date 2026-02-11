# Orket Roadmap

This roadmap tracks only unfinished work.
Architecture authority: `docs/OrketArchitectureModel.md`.
Last updated: 2026-02-11.

## Open Phases
1. Phase R: Volatility Decomposition (Tools/API/Orchestrator)

### R1. Tool boundary reduction (remaining)
Completed:
1. `ToolBox` remains a composition/runtime shell with strategy-based tool map (`ToolStrategyNode`).

Remaining:
1. Audit `orket/tools.py` and remove any remaining non-forwarding compatibility/business behavior.
2. Move any residual direct wiring in `ToolBox` into tool family composition seams.

Acceptance:
1. `ToolBox` contains only composition and compatibility forwarding, no business/process logic.
2. `tests/test_toolbox_refactor.py` and `tests/test_decision_nodes_planner.py` stay green.

### R2. API decomposition
Completed:
1. Extracted API policy decisions into `ApiRuntimeStrategyNode` for:
   - CORS origin parsing
   - API key validation policy
   - run-active invocation policy
   - clear-logs target path
   - metrics normalization
   - calendar window resolution
   - explorer path/filter/sort
   - preview target + preview invocation selection
   - run metrics workspace resolution
   - sandbox workspace + execution-pipeline creation
   - chat driver creation
   - websocket removal policy

Remaining:
1. Continue shrinking `orket/interfaces/api.py` by moving remaining endpoint wiring/construction logic into runtime seams where volatility is expected.
2. Keep FastAPI handlers transport-only (validation, status codes, serialization).

Acceptance:
1. API file size/churn trend decreases across subsequent churn reports.
2. Existing API regression tests remain green.

### R3. Orchestrator decomposition
Completed:
1. Extracted loop policy decisions to `OrchestrationLoopPolicyNode` for:
   - concurrency limit
   - max iterations
   - context window
   - review-turn detection
   - turn status selection
   - role ordering for review turns
   - missing-seat status

Remaining:
1. Continue extracting turn lifecycle policy branches from `_execute_issue_turn` and failure paths.
2. Keep `execute_epic` loop shape stable while moving branch decisions behind node seams.

Acceptance:
1. `execute_epic` remains behaviorally equivalent under current test suite.
2. Orchestrator policy changes can be done via nodes/seams with no loop-shape changes.

## Verification Baseline
1. `python -m pytest tests/ -q` -> 210 passed.
2. `python -m pytest --collect-only -q` -> 210 collected.

## Working Model

Use `Exists -> Working -> Done`:
1. Exists: item defined here with acceptance criteria.
2. Working: item has explicit `Completed` and `Remaining` bullets in this file.
3. Done: verified and removed from roadmap with one `CHANGELOG.md` line.
