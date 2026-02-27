# Contributor Guide

Orket

## Protocol
1. Start each session by reading:
   - this file
   - `docs/CONTRIBUTOR.md`
   - `docs/ROADMAP.md`
   - `docs/ARCHITECTURE.md`
2. Update `docs/ROADMAP.md` at handoff: remove completed work and obsolete work.
   - If a project is complete, move its plan/spec docs to `docs/projects/archive/<ProjectName>/` and update links.
   - Keep `docs/ROADMAP.md` as the only active roadmap source; do not create parallel active backlog docs.
   - Run anti-orphan checks at handoff:
     1) every non-archive folder in `docs/projects/` appears in roadmap Project Index
     2) every active/queued roadmap entry points to an existing path
3. Keep runtime paths in `orket/` async-safe and governance mechanical.
4. Do not scan dependency/vendor trees (`node_modules/`, `ui/node_modules/`, `.venv/`) unless explicitly requested.
5. For documentation dates (`Last updated:`), use local `America/Denver` date, not UTC.
6. No session narrative here. Use temporary scratch notes if needed.
7. The roadmap has the next steps, no need to journal them here.
8. Command intent rule:
   - If the user says "follow roadmap" (or equivalent) without naming a project, execute the highest-priority active item in `docs/ROADMAP.md`.
   - Do not switch to paused/deferred projects unless the user explicitly requests it.
   - For `core-pillars`, execute in the exact order defined by `docs/projects/core-pillars/08-DETAILED-SLICE-EXECUTION-PLAN.md`.
9. Published artifacts rule:
   - `benchmarks/published/index.json` is canonical.
   - After any published artifact change, run:
     1) `python scripts/sync_published_index.py --write`
     2) `python scripts/sync_published_index.py --check`
   - Commit `index.json`, generated `README.md`, and artifact files together.

## Current Focus
1. Keep `docs/ROADMAP.md` active-only (remove completed/obsolete items at each handoff).
2. Preserve deterministic green gates (`pytest`, dependency direction, volatility boundaries).
3. Keep pilot evidence artifacts current (`architecture_pilot_matrix*`, `microservices_pilot_stability_check.json`).
4. Execute `core-pillars` as the default active roadmap lane unless the user redirects.
5. Execute `core-pillars` by slice (`CP-1.1 -> CP-1.2 -> ...`), not by pillar batch.

## Quick Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Create local `.env` for secrets.
3. Run locally: `python main.py --rock <rock_name>`

## Core Rules
1. Keep permanent decisions in tracked docs/code.
2. Keep runtime paths in `orket/` async-safe (no blocking I/O).
3. Keep governance mechanical (no retry theater).
4. Prefer small, reversible changes.
5. Do not commit secrets, `.env`, or local database files.
6. Keep repo root clean; do not add tool-specific metadata folders in root when they can live under `Agents/`.
7. CI/workflow policy: use `.gitea/workflows/` only.
8. Do not add or modify `.github/workflows/*` unless explicitly requested by the project owner in the current task.
9. When adding or changing automation, implement and validate the `.gitea` workflow first; treat GitHub workflow paths as out of scope by default.

## Project Map
- Rocks: `model/core/rocks/`
- Epics: `model/core/epics/`
- Roles: `model/core/roles/`
- Dialects: `model/core/dialects/`

## How To Work
1. Pick one roadmap item.
   - Default selection: highest-priority active (non-paused) roadmap item.
   - If that item is `core-pillars`, use `08-DETAILED-SLICE-EXECUTION-PLAN.md` as the implementation source of truth.
2. Implement the smallest complete slice.
3. Add/update tests for behavior changed.
4. Run targeted tests first, then broader tests.
5. Update docs affected by behavior changes.

## Testing
1. Real-world first: prefer temporary real filesystems/databases over mocks.
2. Keep tests deterministic and isolated.
3. For refactors, prove parity with regression tests.

## Common Additions
1. New role: add `model/core/roles/<role>.json`.
2. New tool: implement in tool family/runtime seam and wire via decision strategy/tool map.
3. New epic: add `model/core/epics/<epic>.json` with atomic issues.

## PR Checklist
1. Clear summary of what changed and why.
2. Tests run and results listed.
3. Risk/rollback notes for non-trivial changes.
4. Docs updated where behavior changed.
5. Workflow changes (if any) are limited to `.gitea/workflows/` unless explicitly approved otherwise.
6. Boundary/contract breaks include a proposal using `docs/architecture/CONTRACT_DELTA_TEMPLATE.md` with migration and rollback plans.
7. Published artifact updates include synchronized `benchmarks/published/index.json` and `benchmarks/published/README.md`.
