# Orket Roadmap

This roadmap tracks only unfinished work.
Architecture authority: `docs/OrketArchitectureModel.md`.

## Current State

The prior release gate is complete:
1. `python -m pytest tests/ -q` -> 175 passed.
2. `python -m pytest --collect-only -q` -> 175 collected.
3. `rg -n "except Exception" orket` -> 0 matches.
4. Load artifact archived: `benchmarks/results/2026-02-11_phase5_load.json`.
5. CI includes `quality`, `docker_smoke`, and `migration_smoke` jobs.

## Phase F: Architecture Completion

Goal: finish dogfooding the architecture by reducing volatile behavior remaining in orchestration and runtime seams.

1. Extract remaining orchestration volatility into Decision Nodes where churn is high.
- Start with post-turn policy/evaluator internals only if behavior change frequency justifies extraction.
- Keep stable orchestration wiring in `Orchestrator`.
2. Add Decision Node configuration docs with examples in `docs/`:
- planner override
- router override
- prompt strategy override
- evaluator override
3. Add one end-to-end plugin override test proving runtime selects a non-default node from `organization.process_rules`.

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
