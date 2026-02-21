# Contributor Guide

This guide is human/agent agnostic.

## Protocol
1. Start each session by reading:
   - this file
   - `docs/CONTRIBUTOR.md`
   - `docs/ROADMAP.md`
   - `docs/ARCHITECTURE.md`
2. Update `docs/ROADMAP.md` at handoff: remove completed work and obsolete work.
   - If a project is complete, move its plan/spec docs to `docs/archive/<ProjectName>/` and update links.
3. Keep runtime paths in `orket/` async-safe and governance mechanical.
4. Do not scan dependency/vendor trees (`node_modules/`, `ui/node_modules/`, `.venv/`) unless explicitly requested.
5. For documentation dates (`Last updated:`), use local `America/Denver` date, not UTC.
6. No session narrative here. Use temporary scratch notes if needed.
7. The roadmap has the next steps, no need to journal them here.

## Current Focus
1. Keep `docs/ROADMAP.md` active-only (remove completed/obsolete items at each handoff).
2. Preserve deterministic green gates (`pytest`, dependency direction, volatility boundaries).
3. Keep pilot evidence artifacts current (`architecture_pilot_matrix*`, `microservices_pilot_stability_check.json`).

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

## Project Map
- Rocks: `model/core/rocks/`
- Epics: `model/core/epics/`
- Roles: `model/core/roles/`
- Dialects: `model/core/dialects/`

## How To Work
1. Pick one roadmap item.
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
