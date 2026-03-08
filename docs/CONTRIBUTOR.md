# Contributor Guide

Orket

## Protocol
1. Start each session by reading:
   - this file
   - `docs/CONTRIBUTOR.md`
   - `docs/ROADMAP.md`
   - `docs/ARCHITECTURE.md`
   - Complete this startup read before beginning work in the repository.
   - Agent-specific enforcement details live in `AGENTS.md`.
2. Update `docs/ROADMAP.md` at handoff: remove completed work and obsolete work.
   - Interpretation rule:
     1) `Priority Now` empty means no priority lane, not no work
     2) active items in `Maintenance (Non-Priority)` remain executable and are the default queue when no priority lane exists
   - If a non-maintenance project or project lane is complete, move its closeout/plan/history docs to `docs/projects/archive/<ProjectName>/` and update links in the same change.
   - Project-owned docs that remain long-lived contracts/specifications must move to `docs/specs/` when the project or lane is archived.
   - Completed non-maintenance project folders must not remain under `docs/projects/` unless the folder is still intentionally active as a maintenance lane or externally gated authority surface.
   - Keep `docs/ROADMAP.md` as the only active roadmap source; do not create parallel active backlog docs.
   - When creating a new active implementation plan, add or update the corresponding `docs/ROADMAP.md` entry in the same change so the plan is discoverable from the active execution index.
   - Roadmap entries for active plans should stay terse and point to the canonical plan path instead of restating the plan body.
   - Keep `docs/ROADMAP.md` active-only: do not leave completed or archived project roots in active roadmap sections or the Project Index.
   - Formal closeout handshake for any completed project lane or techdebt cycle:
     1) update roadmap status and next-slice selection in the same change
     2) move completed cycle/project docs into the proper archive folder in the same change
     3) leave no `Status: Completed` or `Status: Archived` cycle doc in active `docs/projects/` scope after handoff
     4) for `docs/projects/techdebt/`, leave only standing maintenance docs plus docs for cycle ids still listed as active in `docs/ROADMAP.md`
     5) preserve discoverability with archive links, not by leaving completed docs in active folders
   - Run anti-orphan checks at handoff:
     1) every remaining non-archive folder in `docs/projects/` appears in roadmap Project Index
     2) every active/queued roadmap entry points to an existing path
     3) run `python scripts/governance/check_docs_project_hygiene.py` and fix all failures before handoff
3. Contract extraction prework rule:
   - When requirements for a project or lane are accepted and durable contracts/specifications are now clear, extract those contract/spec portions into `docs/specs/` before creating the implementation plan.
   - Requirement documents may keep narrative, rationale, scope, and acceptance framing, but implementation plans should cite the extracted spec/contract files as authority instead of depending on requirement docs that will later be archived.
   - Do not wait until archive/closeout time to discover and move long-lived authority out of `docs/projects/`.
4. Keep runtime paths in `orket/` async-safe and governance mechanical.
5. Do not scan dependency/vendor trees (`node_modules/`, `ui/node_modules/`, `.venv/`) unless explicitly requested.
6. For documentation dates (`Last updated:`), use local `America/Denver` date, not UTC.
7. No session narrative here. Use temporary scratch notes if needed.
8. The roadmap has the next steps, no need to journal them here.
9. Command intent rule:
   - If the user says "follow roadmap" (or equivalent) without naming a project, execute the highest-priority active item in `docs/ROADMAP.md`.
   - If `Priority Now` is empty, execute the highest-priority active item under `Maintenance (Non-Priority)` before considering staged or future lanes.
   - Do not switch to paused/deferred projects unless the user explicitly requests it.
10. Published artifacts rule:
   - `benchmarks/published/index.json` is canonical.
   - After any published artifact change, run:
     1) `python scripts/governance/sync_published_index.py --write`
     2) `python scripts/governance/sync_published_index.py --check`
   - Commit `index.json`, generated `README.md`, and artifact files together.
11. Recurring maintenance rule:
   - Recurring freshness/maintenance cycles are governed by:
     `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`
   - Techdebt folder closure/archive semantics are governed by:
     `docs/projects/techdebt/README.md`
   - Keep recurring checks out of project execution lanes; project plans should remain closable.
12. Techdebt cycle closure rule:
   - If a techdebt cycle's implementation requirements are complete and verified, move cycle-specific docs from
     `docs/projects/techdebt/` to `docs/projects/archive/techdebt/<cycle_id>/` in the same closeout change.
   - Archive both cycle implementation artifacts and cycle requirement/review/spec files covered by that closeout.
   - Keep only standing maintenance docs (and any currently active cycle docs) under `docs/projects/techdebt/`.
13. README discipline rule:
   - Do not add small project-subfolder `README.md` files by default.
   - Allowed exceptions are maintained index/gateway docs (for example root README, scripts/index readmes, or explicitly referenced governance docs with a named owner).
   - Prefer `docs/ROADMAP.md`, `docs/CONTRIBUTOR.md`, and contract/spec documents as the durable source of truth.

## Current Focus
1. Keep `docs/ROADMAP.md` active-only (remove completed/obsolete items at each handoff).
2. Preserve deterministic green gates (`pytest`, dependency direction, volatility boundaries).
3. Keep pilot evidence artifacts current (`architecture_pilot_matrix*`, `microservices_pilot_stability_check.json`).
4. Execute the highest-priority active roadmap lane unless the user redirects.
5. For recurring maintenance cycles, execute `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`.

## Quick Setup
1. Install dependencies: `python -m pip install --upgrade pip && python -m pip install -e ".[dev]"`
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
2. Implement the smallest complete slice.
3. Add/update tests for behavior changed.
4. Run targeted tests first, then broader tests.
5. Update docs affected by behavior changes.

## Testing
1. Real-world first: prefer temporary real filesystems/databases over mocks.
2. Keep tests deterministic and isolated.
3. For refactors, prove parity with regression tests.
4. Provider-backed runtime selection and local warmup are authoritative in `orket/runtime/provider_runtime_target.py`; runtime paths and provider verification scripts must reuse that shared path instead of carrying separate provider/model resolution logic.

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
