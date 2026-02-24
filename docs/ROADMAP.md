# Orket Roadmap

Last updated: 2026-02-24

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: `core-pillars`.

## Priority Now
1. `core-pillars`: execute by canonical slice plan (`docs/projects/core-pillars/08-DETAILED-SLICE-EXECUTION-PLAN.md`), current active slice `CP-2.2`.
2. `core-pillars`: active requirements/contracts (`docs/projects/core-pillars/01-REQUIREMENTS.md`).
3. `core-pillars`: milestone tracking (`docs/projects/core-pillars/03-MILESTONES.md`).
4. `OS`: paused/deferred while pillar-first path is validated (`docs/projects/OS/NEXT_PART_V1_REQUIREMENTS.md`).
5. `ideas`: intake-only backlog (must be promoted to dedicated project folder before execution).
6. `modularity-refactor`: completed and archived (`docs/projects/archive/Modularity-Refactor-2026-02-24/`).

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| core-pillars | active | P1 | `docs/projects/core-pillars/` | Orket Core | Execute by `08-DETAILED-SLICE-EXECUTION-PLAN.md` (slice-first, not pillar batching). |
| OS | queued | P2 | `docs/projects/OS/` | Orket Core | Paused/deferred while core-pillars track establishes near-term use-case fit. |
| ideas | queued | P3 | `docs/projects/ideas/` | Orket Core | Intake-only. Keep empty except pointer/index notes. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
