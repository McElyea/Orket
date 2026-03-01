# Orket Roadmap

Last updated: 2026-02-28

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: `SDK`.

## Priority Now
1. `SDK` (P1, active): execute current SDK plan in `docs/projects/SDK/`.
2. `reforger-textmystery-adapter` (P2, queued): v0 compiler-style reforger route and canonical blob round-trip.
3. `reforger` (completed): archived at `docs/projects/archive/Reforger-2026-02-28/`.

## Active Execution
1. `SDK` is the active lane.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| SDK | active | P1 | `docs/projects/SDK/` | Orket Core | Active roadmap lane. Phase 2 complete; Phase 3 bridge-side SDK integration started; Phase 5 docs and Phase 6 hardening in progress. |
| reforger-textmystery-adapter | queued | P2 | `docs/projects/reforger-textmystery-adapter/` | Orket Core | v0 normalize/reforge/materialize route with deterministic artifacts. |
| techdebt | active | P3 | `docs/projects/techdebt/` | Orket Core | Security fixes, exception narrowing, test gaps, structural cleanup. Fix opportunistically. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
