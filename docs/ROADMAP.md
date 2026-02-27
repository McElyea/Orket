# Orket Roadmap

Last updated: 2026-02-27

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: `RefactorCardEngine`.

## Priority Now
1. `RefactorCardEngine`: active (`docs/projects/RefactorCardEngine/`).
2. `OS`: paused/deferred while pillar-first path is validated (`docs/projects/OS/NEXT_PART_V1_REQUIREMENTS.md`).
3. `ideas`: intake-only backlog (must be promoted to dedicated project folder before execution).
4. `odr`: completed and archived (`docs/projects/archive/ODR-2026-02-26/`).
5. `docs-gate`: completed and archived (`docs/projects/archive/Docs-Gate-2026-02-25/`).
6. `modularity-refactor`: completed and archived (`docs/projects/archive/Modularity-Refactor-2026-02-24/`).

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| RefactorCardEngine | active | P1 | `docs/projects/RefactorCardEngine/` | Orket Core | Unify Cards+ODR under shared workload contract, then migrate card hierarchy to parent-tree profiles. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| OS | queued | P2 | `docs/projects/OS/` | Orket Core | Paused/deferred while core-pillars track establishes near-term use-case fit. |
| ideas | queued | P3 | `docs/projects/ideas/` | Orket Core | Intake-only. Keep empty except pointer/index notes. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
