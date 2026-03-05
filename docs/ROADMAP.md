# Orket Roadmap

Last updated: 2026-03-04

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: marshaller.

## Priority Now
1. marshaller -- Marshaller v0 specification/implementation lane.
2. protocol-governed -- Runtime protocol determinism hardening (requirements v5.1 + implementation plan).
3. NervousSystem -- v1 complete; hold for review and next-phase planning.

## Active Execution
1. marshaller -- Execute v0 slices from `docs/projects/marshaller/Marshaller-v0.md` (completed: Stage 0/1 intake + Stage 2/3/4 single-attempt runner baseline + replay equivalence output; next: promotion event + multi-attempt orchestration).

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| NervousSystem | active | P2-review | `docs/projects/future/NervousSystem/` | Orket Core | Locked v1 action-path plan implemented with live evidence at `benchmarks/results/nervous_system_live_evidence.json` and verification notes in `docs/projects/future/NervousSystem/LIVE_VERIFICATION.md`. |
| marshaller | active | P1-active | `docs/projects/marshaller/` | Orket Core | Marshaller v0 implementation in progress; baseline includes intake contracts, patch apply, deterministic gates, hash-chained ledger artifacts, and replay equivalence output. |
| protocol-governed | queued | P2-queued | `docs/projects/protocol-governed/` | Orket Core | Runtime contract lane with v5.1 requirements and implementation sequencing plan. |
| future | backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred project lanes (for example `UIForge`, `NervousSystem`). |
| LieDetector | completed-archive | complete | `docs/projects/archive/LieDetector/` | Orket Core | Archived project lane; v1 completed and moved to archive. |
| techdebt | completed-archive | complete | `docs/projects/archive/TechDebt-2026-03-02/` | Orket Core | Review3 remediation lane closed (C1-C6 complete; security gates green). Deferred medium backlog documented in archive README/plan. |
| SDK-2026-03-01-Audio | completed-archive | complete | `docs/projects/archive/SDK-2026-03-01-Audio/` | Orket Core | SDK typed audio capabilities, Piper/audio backend wiring, bridge integration, and reforger voice-profile validation completed in-repo. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| RuleSim-2026-03-01 | completed-archive | complete | `docs/projects/archive/RuleSim-2026-03-01/` | Orket Core | RuleSim v0 implemented; docs archived after completion. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
