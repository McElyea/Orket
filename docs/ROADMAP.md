# Orket Roadmap

Last updated: 2026-03-02

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: LieDetector.

## Priority Now
1. LieDetector -- Maintenance and polish for floor-progression truth/lie deduction game with TUI.
2. marshaller -- Marshaller v0 specification/implementation lane.

## Active Execution
1. LieDetector -- v1 complete; keep in maintenance unless new feature scope is requested.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| LieDetector | active-maintenance | P2-active | `docs/projects/LieDetector/` | Orket Core | Standalone "20 questions with a twist" deduction game. Persona system, SDK TUI, PolicyGate, ANSI renderer. v1 decoupled from mystery world. |
| marshaller | queued | P2-queued | `docs/projects/marshaller/` | Orket Core | Marshaller v0 specification and implementation lane. |
| future | backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred project lanes (for example `UIForge`, `NervousSystem`). |
| techdebt | completed-archive | complete | `docs/projects/archive/TechDebt-2026-03-02/` | Orket Core | Review3 remediation lane closed (C1-C6 complete; security gates green). Deferred medium backlog documented in archive README/plan. |
| SDK-2026-03-01-Audio | completed-archive | complete | `docs/projects/archive/SDK-2026-03-01-Audio/` | Orket Core | SDK typed audio capabilities, Piper/audio backend wiring, bridge integration, and reforger voice-profile validation completed in-repo. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| RuleSim-2026-03-01 | completed-archive | complete | `docs/projects/archive/RuleSim-2026-03-01/` | Orket Core | RuleSim v0 implemented; docs archived after completion. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
