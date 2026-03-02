# Orket Roadmap

Last updated: 2026-03-02

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: techdebt.

## Priority Now
1. techdebt -- Execute `docs/projects/techdebt/IMPLEMENTATION-PLAN.md` from `docs/projects/techdebt/Review3.md`.
2. LieDetector -- Maintenance and polish for floor-progression truth/lie deduction game with TUI.
3. marshaller -- Marshaller v0 specification/implementation lane.

## Active Execution
1. techdebt -- Review3 remediation implementation planning and execution active in `docs/projects/techdebt/`.
2. LieDetector -- v1 complete; keep in maintenance unless new feature scope is requested.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| techdebt | active | P1-active | `docs/projects/techdebt/` | Orket Core | Active Review3 lane. Canonical docs: `Review3.md` and `IMPLEMENTATION-PLAN.md`. |
| LieDetector | active-maintenance | P2-active | `docs/projects/LieDetector/` | Orket Core | Standalone "20 questions with a twist" deduction game. Persona system, SDK TUI, PolicyGate, ANSI renderer. v1 decoupled from mystery world. |
| marshaller | queued | P2-queued | `docs/projects/marshaller/` | Orket Core | Marshaller v0 specification and implementation lane. |
| future | backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred project lanes (for example `UIForge`, `NervousSystem`). |
| SDK-2026-03-01-Audio | completed-archive | complete | `docs/projects/archive/SDK-2026-03-01-Audio/` | Orket Core | SDK typed audio capabilities, Piper/audio backend wiring, bridge integration, and reforger voice-profile validation completed in-repo. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| RuleSim-2026-03-01 | completed-archive | complete | `docs/projects/archive/RuleSim-2026-03-01/` | Orket Core | RuleSim v0 implemented; docs archived after completion. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
