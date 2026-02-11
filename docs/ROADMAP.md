# Orket Roadmap

This roadmap tracks only unfinished work.
Architecture authority: `docs/OrketArchitectureModel.md`.

## Open Phases
1. Phase R: Volatility Decomposition (Tools/API/Orchestrator)

### R1. Tool boundary reduction (remaining)
1. Reduce direct tool wiring in `orket/tools.py` by moving residual mixed responsibilities into tool families.
2. Keep `ToolBox` as composition/runtime shell only.

Acceptance:
1. `ToolBox` contains only composition and compatibility forwarding, no business/process logic.
2. `tests/test_toolbox_refactor.py` and `tests/test_decision_nodes_planner.py` stay green.

### R2. API decomposition
1. Extract endpoint decision/policy selection from `orket/interfaces/api.py` into runtime/decision seams.
2. Keep FastAPI layer focused on transport concerns (request/response/status codes).

Acceptance:
1. API file size/churn trend decreases across subsequent churn reports.
2. Existing API regression tests remain green.

### R3. Orchestrator decomposition
1. Separate turn lifecycle policies from stable loop mechanics in `orket/orchestration/orchestrator.py`.
2. Minimize direct policy branching in the core loop.

Acceptance:
1. `execute_epic` remains behaviorally equivalent under current test suite.
2. Orchestrator policy changes can be done via nodes/seams with no loop-shape changes.

## Verification Baseline
1. `python -m pytest tests/ -q` -> 210 passed.
2. `python -m pytest --collect-only -q` -> 210 collected.

## Working Model

Use `Exists -> Working -> Done`:
1. Exists: item defined here with acceptance criteria.
2. Working: one active note in `Agents/HANDOFF.md`.
3. Done: verified and removed from roadmap with one `CHANGELOG.md` line.
