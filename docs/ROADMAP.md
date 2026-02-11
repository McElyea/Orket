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

## Phase F: Architecture Completion

Goal: finish dogfooding the architecture by reducing volatile behavior remaining in orchestration and runtime seams.

Planning decisions (locked for this phase):
1. Current runtime behavior remains the default baseline (no attempt to force "plugin purity" upfront).
2. First decomposition target is `tools.py`.
3. Plugin resolution supports config + environment override.
4. Controlled behavior changes are allowed during extraction when explicitly documented and tested.
5. Keep a monorepo structure (no repo split in this phase).
6. Contract tests + parity tests are required before enabling non-default nodes.

Working assumptions (can be revised):
1. Ownership model: shared ownership for now; revisit when stable node families emerge.
2. Completion artifact: roadmap milestones + target folder architecture + dependency rules.

Remaining milestones:
1. Documentation:
- Publish folder architecture and dependency direction rules in `docs/`.
- Document config + env override examples.

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
