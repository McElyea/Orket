# Orket Roadmap

Last updated: 2026-02-24

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
| OS | active | P1 | `docs/projects/OS/` | Orket Core | Execute `docs/projects/OS/IMPLEMENTATION_PLAN.md`; kernel-law tests are consolidated under `tests/kernel/v1`, registry audit is strict fail-closed, capability metadata is wired to runtime artifact `model/core/contracts/kernel_capability_policy_v1.json`, replay parity asserts deterministic mismatch fields over contract-scoped vectors (including event-code multiset, mixed turn-count, and mixed issue-order normalization), policy artifact schema enforcement is active, explicit kernel API surface is exported from `orket/kernel/v1/api.py`, and orchestration integration now routes through `KernelV1Gateway`; next focus is minimal workflow lifecycle execution path + orchestration-facing replay-compare boundary tests. |
| modularize | completed | n/a | `docs/projects/archive/Modularize/` | Orket Core | Archived and closed. |
| ideas | queued | P2 | `docs/projects/ideas/` | Orket Core | Input backlog only; promote to active only after roadmap reprioritization. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
