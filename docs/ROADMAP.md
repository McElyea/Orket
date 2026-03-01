# Orket Roadmap

Last updated: 2026-03-01

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: `techdebt`.

## Priority Now
1. `techdebt` (P1, active): security fixes, exception narrowing, test gaps, structural cleanup.
2. `SDK` (completed): archived at `docs/projects/archive/SDK-2026-03-01/`.
3. `reforger-textmystery-adapter` (completed): archived at `docs/projects/archive/Reforger-TextMystery-Adapter-2026-03-01/`.
4. `reforger` (completed): archived at `docs/projects/archive/Reforger-2026-02-28/`.

## Active Execution
1. `techdebt` is the active lane.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| techdebt | active | P1 | `docs/projects/techdebt/` | Orket Core | Active roadmap lane; Phase 1 security slice in progress (`TD-SEC-1a/b/c` complete). |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
