# Orket Roadmap

Last updated: 2026-02-28

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: `model-streaming`.

## Priority Now
1. `model-streaming`: active (`docs/projects/model-streaming/01-IMPLEMENTATION-PLAN.md`).
2. `extensions`: completed and archived (`docs/projects/archive/Extensions-2026-02-28/`).
3. `streamevents`: completed and archived (`docs/projects/archive/StreamEvents-2026-02-28/`).
4. `RefactorCardEngine`: completed and archived (`docs/projects/archive/RefactorCardEngine-2026-02-28/`).
5. `OS`: stale and archived (`docs/projects/archive/OS-Stale-2026-02-28/`).
6. `odr`: completed and archived (`docs/projects/archive/ODR-2026-02-26/`).
7. `docs-gate`: completed and archived (`docs/projects/archive/Docs-Gate-2026-02-25/`).
8. `modularity-refactor`: completed and archived (`docs/projects/archive/Modularity-Refactor-2026-02-24/`).

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| model-streaming | active | P1 | `docs/projects/model-streaming/` | Orket Core | Integrate provider-driven real model streaming while preserving stream laws and deterministic authority boundaries. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
