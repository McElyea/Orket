# Orket Roadmap

Last updated: 2026-02-28

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: `reforger` (Layer 0).

## Priority Now
1. `reforger` (P0, active): execute Layer 0 plan from `docs/projects/reforger/02-PR-PLAN.md`.
2. `SDK` (P1, queued): resume only after `reforger` Layer 0 exit criteria are met.

## Active Execution
1. `reforger` started: PR1 (`Pack + Mode Schema + Validation`).
2. Immediate deliverables:
   - Scaffold `orket/reforger/` module boundaries from requirements.
   - Implement pack and mode schema validation with deterministic inheritance resolution.
   - Add PR1 unit tests for inheritance precedence, missing required files, and mode schema validation.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| reforger | active | P0 | `docs/projects/reforger/` | Orket Core | Layer 0 requirements and PR plan approved; execution starts at PR1. |
| SDK | queued | P1 | `docs/projects/SDK/` | Orket Core | Queued behind Reforger Layer 0. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
