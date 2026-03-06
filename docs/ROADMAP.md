# Orket Roadmap

Last updated: 2026-03-06

## Priority Plan Pointer
1. techdebt recurring maintenance checklist: `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`
2. techdebt hardening implementation plan: `docs/projects/techdebt/TD03052026-Plan.md`
3. marshaller requirements plan: `docs/projects/marshaller/Marshaller-v0.md`

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: techdebt.

## Priority Now
1. techdebt -- Standing recurring maintenance lane for gate freshness, protocol window checks, local prompting promotion readiness, and checklist curation.
2. marshaller -- Marshaller v0 scaffolding lane aligned to protocol-governed runtime decisions.
3. NervousSystem -- v1 complete; hold for review and next-phase planning.
4. protocol-governed -- Execution complete; reopen only with explicit scoped changes beyond checklist maintenance.

## Active Execution
1. techdebt -- Execute `docs/projects/techdebt/Recurring-Maintenance-Checklist.md` each cycle and keep it curated to prevent checklist bloat.
2. marshaller -- Treat current implementation as scaffolding and only adjust where protocol-governed contracts require alignment.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| NervousSystem | active | P2-review | `docs/projects/future/NervousSystem/` | Orket Core | Locked v1 action-path plan implemented with live evidence at `benchmarks/results/nervous_system_live_evidence.json` and verification notes in `docs/projects/future/NervousSystem/LIVE_VERIFICATION.md`. |
| marshaller | active | P2-scaffolding | `docs/projects/marshaller/` | Orket Core | Current Marshaller implementation is scaffolding and will be refit to finalized protocol-governed runtime decisions. |
| techdebt | active | P1-recurring | `docs/projects/techdebt/` | Orket Core | Standing maintenance lane. Run `Recurring-Maintenance-Checklist.md` each cycle, keep `G1`-`G7`/protocol/local-prompting freshness artifacts current, and curate checklist scope to avoid bloat. |
| protocol-governed | active | P1-closed | `docs/projects/protocol-governed/` | Orket Core | v5.1 implementation is complete; recurring freshness work moved to `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`. |
| future | backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred project lanes (for example `UIForge`, `NervousSystem`). |
| LieDetector | completed-archive | complete | `docs/projects/archive/LieDetector/` | Orket Core | Archived project lane; v1 completed and moved to archive. |
| SDK-2026-03-01-Audio | completed-archive | complete | `docs/projects/archive/SDK-2026-03-01-Audio/` | Orket Core | SDK typed audio capabilities, Piper/audio backend wiring, bridge integration, and reforger voice-profile validation completed in-repo. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| RuleSim-2026-03-01 | completed-archive | complete | `docs/projects/archive/RuleSim-2026-03-01/` | Orket Core | RuleSim v0 implemented; docs archived after completion. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
