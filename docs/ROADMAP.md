# Orket Roadmap

This roadmap tracks only unfinished work.
Architecture authority: `docs/OrketArchitectureModel.md`.

## Phase A: Stabilize Test Contract

Goal: Full green suite with runtime-aligned tests.

1. Completed:
- `tests/test_async_card_repository.py` aligned with `IssueRecord` contract (`seat` required, async DB import fixed).
- `tests/test_gitea_webhook.py` aligned with async `WebhookDatabase` behavior (stale sqlite patching removed).
- `tests/test_sandbox_compose_generation.py` aligned with `_generate_compose_file(..., db_password=...)`.
- `tests/test_orchestrator_epic.py` fixtures aligned with current runtime assumptions (`epic.references`, ready-candidate mocks).
2. Verification complete:
- Full suite green: `python -m pytest tests/ -q` -> 156 passed.
- Test collection target exceeded: `python -m pytest --collect-only -q` -> 156 collected.

## Phase B: Exception Boundary Hardening

Goal: Remove broad catch-all handling in runtime paths.

1. Completed:
- Removed broad `except Exception` handlers across `orket/`.
- Replaced with typed exception boundaries and explicit fallback behavior.
2. Verification:
- `rg -n "except Exception" orket` -> 0 matches.

## Phase C: Performance and Load Evidence

Goal: Generate and store repeatable performance evidence.

1. Completed benchmark scenarios:
- 100 webhook deliveries.
- 10 parallel epic trigger executions.
- 50 websocket clients.
2. Archived results:
- `benchmarks/results/2026-02-11_phase5_load.json`
3. Runbook linkage completed:
- `docs/RUNBOOK.md` references command + archived artifact.

## Phase D: Release Pipeline Closure

Goal: Prove deployability from source to running service.

1. Completed:
- Added `docker_smoke` CI job (build + run + `/health` probe).
- Added `migration_smoke` CI job (runtime DB + webhook DB migration validation).
- Added release checklist section in `docs/RUNBOOK.md` referencing Docker, migrations, and benchmark artifacts.

## Phase E: Architecture Dogfood Migration

Goal: Run Orket using the same volatility-first architecture it prescribes.

1. Define stable contracts for volatile Decision Nodes:
- Planner
- Router
- Evaluator
- Prompt Strategy / Model Selection
2. Add plugin registry and resolver for Decision Node implementations.
3. Keep current runtime behavior as default built-in plugins.
4. Extract one volatile path at a time behind contracts:
- Start with planning/routing.
- Then evaluation/prompting.
5. Add contract tests per Decision Node interface.
6. Make Orchestrator responsible for stable flow only (wiring + governance + persistence).

## Management Model: Exists -> Working -> Done

Goal: Use one explicit, low-noise system for coordination and handoff.

1. `Exists`:
- Item is defined in this roadmap with an owner and acceptance criteria.
- No activity log entry required yet.
2. `Working`:
- Item is active and has one short active record in `Agents/HANDOFF.md`.
- Work notes remain local and temporary.
3. `Done`:
- Acceptance criteria are verified.
- Add one line in `CHANGELOG.md` and remove the item from roadmap.

Operating rules:
1. `docs/ROADMAP.md` is the only source of planned work.
2. `Agents/HANDOFF.md` is the only source of current in-flight context.
3. `Agents/GLOBAL_ACTIVITY.md` should be treated as optional legacy history, not a planning tool.
4. If the same detail appears in multiple places, keep it in roadmap/handoff and delete duplicates.

## Release Gate

v0.4.0 is ready only when all of the following are true:

1. `python -m pytest tests/ -q` is fully green.
2. Test collection is at least 150.
3. Runtime broad catch-all handlers are removed or explicitly justified at boundaries.
4. Benchmark artifacts for target load are committed.
5. CI validates Docker startup, health, and migrations.
