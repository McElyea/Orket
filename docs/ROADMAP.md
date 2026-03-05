# Orket Roadmap

Last updated: 2026-03-04

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: protocol-governed.

## Priority Now
1. protocol-governed -- Runtime protocol determinism hardening (requirements v5.1 + implementation plan).
2. marshaller -- Marshaller v0 scaffolding lane aligned to protocol-governed runtime decisions.
3. NervousSystem -- v1 complete; hold for review and next-phase planning.

## Active Execution
1. protocol-governed -- Execute implementation plan from `docs/projects/protocol-governed/implementation-plan.md` (in progress: PR-04/PR-08/PR-09 rollout with run-ledger mode selection (`sqlite`/`protocol`/`dual_write`), dual-write parity telemetry, run-level protocol receipt materialization/cross-linking, replay comparator receipt inventory diffs, and campaign surfaces across script/CLI/API; PR-03/PR-06 parser+dispatcher hash/idempotency slices are landed).
2. marshaller -- Treat current implementation as scaffolding and only adjust where protocol-governed contracts require alignment.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| NervousSystem | active | P2-review | `docs/projects/future/NervousSystem/` | Orket Core | Locked v1 action-path plan implemented with live evidence at `benchmarks/results/nervous_system_live_evidence.json` and verification notes in `docs/projects/future/NervousSystem/LIVE_VERIFICATION.md`. |
| marshaller | active | P2-scaffolding | `docs/projects/marshaller/` | Orket Core | Current Marshaller implementation is scaffolding and will be refit to finalized protocol-governed runtime decisions. |
| protocol-governed | active | P1-active | `docs/projects/protocol-governed/` | Orket Core | Primary overhaul lane; strict parser/preflight and hash/idempotency slices are landed, with append-only ledger, replay comparator, and ledger parity cutover scaffolding actively progressing against v5.1. |
| future | backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred project lanes (for example `UIForge`, `NervousSystem`). |
| LieDetector | completed-archive | complete | `docs/projects/archive/LieDetector/` | Orket Core | Archived project lane; v1 completed and moved to archive. |
| techdebt | completed-archive | complete | `docs/projects/archive/TechDebt-2026-03-02/` | Orket Core | Review3 remediation lane closed (C1-C6 complete; security gates green). Deferred medium backlog documented in archive README/plan. |
| SDK-2026-03-01-Audio | completed-archive | complete | `docs/projects/archive/SDK-2026-03-01-Audio/` | Orket Core | SDK typed audio capabilities, Piper/audio backend wiring, bridge integration, and reforger voice-profile validation completed in-repo. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| RuleSim-2026-03-01 | completed-archive | complete | `docs/projects/archive/RuleSim-2026-03-01/` | Orket Core | RuleSim v0 implemented; docs archived after completion. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
