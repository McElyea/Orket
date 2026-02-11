# Orket Roadmap

This roadmap tracks only unfinished work.
Architecture authority: `docs/OrketArchitectureModel.md`.

## Current State

The prior release gate is complete:
1. `python -m pytest tests/ -q` -> 180 passed.
2. `python -m pytest --collect-only -q` -> 180 collected.
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

## Phase H: Volatility Decomposition

Goal: continue dogfooding architecture by extracting the next high-churn volatility seams.

1. Extract API runtime strategy seams from `orket/interfaces/api.py` where behavior is expected to vary.
2. Extract sandbox/runtime policy seams from:
- `orket/services/sandbox_orchestrator.py`
- `orket/orchestration/engine.py`

## Working Model

Use `Exists -> Working -> Done`:
1. Exists: item defined here with acceptance criteria.
2. Working: one active note in `Agents/HANDOFF.md`.
3. Done: verified and removed from roadmap with one `CHANGELOG.md` line.
