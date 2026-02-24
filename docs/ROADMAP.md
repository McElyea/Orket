# Orket Roadmap

Last updated: 2026-02-23

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Priority Now
1. `OS`: active implementation against `docs/projects/OS/IMPLEMENTATION_PLAN.md`.
2. `ideas`: hold as queued input backlog; promote to active when implementation starts.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| OS | active | P1 | `docs/projects/OS/` | Orket Core | Execute `docs/projects/OS/IMPLEMENTATION_PLAN.md`; kernel-law tests are physically consolidated under `tests/kernel/v1`, registry audit is strict fail-closed, schema-contract resolver migration is complete, and thin capability/replay validator handlers + closure-code tests are landed; next focus is policy-backed capability enforcement and replay vector parity depth. |
| modularize | completed | n/a | `docs/projects/archive/Modularize/` | Orket Core | Archived and closed. |
| ideas | queued | P2 | `docs/projects/ideas/` | Orket Core | Input backlog only; promote to active only after roadmap reprioritization. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
