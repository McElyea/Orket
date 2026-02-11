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

## Phase G: Operational Tightening

Goal: close remaining operational risks before broader feature expansion.

1. Replace deprecated FastAPI startup hook with lifespan handlers (`orket/interfaces/api.py`).
2. Add CI artifact upload for load evidence JSON from benchmark runs.
3. Add a one-command local release smoke script that runs:
- tests
- migrations
- docker health check

## Working Model

Use `Exists -> Working -> Done`:
1. Exists: item defined here with acceptance criteria.
2. Working: one active note in `Agents/HANDOFF.md`.
3. Done: verified and removed from roadmap with one `CHANGELOG.md` line.
