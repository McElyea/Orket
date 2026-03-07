# Orket Roadmap

Last updated: 2026-03-06

## Priority Plan Pointer
1. techdebt recurring maintenance checklist (maintenance lane): `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`
2. techdebt folder governance: `docs/projects/techdebt/README.md`
3. core runtime requirements implementation plan (completed lane reference): `docs/projects/core/runtime_requirements_implementation_plan.md`
4. core runtime requirements slice workboard (completed lane tracker): `docs/projects/core/runtime_requirements_slice_workboard.md`
5. protocol-governed staged/waiting source: `docs/projects/archive/protocol-governed/PG03062026/implementation-plan.md`
6. protocol-governed future compatibility source: `docs/projects/protocol-governed/local-prompting-requirements.md`

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project:
1. Execute the highest-priority active (non-paused) item in **Priority Now**.
2. If **Priority Now** is intentionally empty, execute item 1 in **Maintenance (Non-Priority)**.
3. Do not execute **Staged / Waiting** items unless explicitly requested or performing a scheduled review.
Current default target: techdebt maintenance lane.

## Priority Now
Intentionally empty. Core runtime requirements implementation lane is complete (`CORE-IMP-00` through `CORE-IMP-08` all done with proof artifacts).

## Maintenance (Non-Priority)
1. techdebt -- Execute `docs/projects/techdebt/Recurring-Maintenance-Checklist.md` each cycle; keep recurring checks curated and archive closed cycle docs per `docs/projects/techdebt/README.md`.

## Staged / Waiting (Externally Gated)
1. protocol-governed production-window operator sign-off -- Waiting for real production traffic; review cadence monthly; next review `2026-04-06`.
2. protocol-governed post-production six-month evidence -- Waiting for production start date + six-month soak period; review cadence monthly; next review `2026-04-06`.

## Future Lanes (Non-Priority Backlog)
1. protocol-governed local provider compatibility expansion (`vLLM`, `llama.cpp`) -- Future lane only; reopen with explicit scoped implementation request.
2. NervousSystem next-phase planning -- Keep in future lane until production rollout timing is explicitly scheduled.
3. marshaller requirements hardening -- Keep parked until requirements are mature and explicitly approved for execution.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| NervousSystem | future-hold | P3-hold | `docs/projects/future/NervousSystem/` | Orket Core | Locked v1 action-path plan is implemented with live evidence at `benchmarks/results/nervous_system_live_evidence.json` and verification notes in `docs/projects/future/NervousSystem/LIVE_VERIFICATION.md`; keep parked until rollout timing is explicitly scheduled. |
| marshaller | future-hold | P3-scaffolding | `docs/projects/marshaller/` | Orket Core | Marshaller remains scaffolding-only; requirements are not mature enough for priority execution and the lane stays parked until explicit requirements hardening approval. |
| core | completed-requirements | P1-complete | `docs/projects/core/` | Orket Core | Core runtime stability requirements lane is complete (`CORE-IMP-00` through `CORE-IMP-08`). Canonical requirement sources remain `runtime_stability_focus_requirements.md`, `core_tool_rings_compatibility_requirements.md`, `tool_contract_template.md`, and `runtime_invariants.md`; implementation closeout evidence remains in `runtime_requirements_implementation_plan.md` and `runtime_requirements_slice_workboard.md`. |
| techdebt | maintenance | P3-maintenance | `docs/projects/techdebt/` | Orket Core | Standing maintenance lane. Run `Recurring-Maintenance-Checklist.md` each cycle, keep `G1`-`G7`/protocol/local-prompting freshness artifacts current, and apply `techdebt/README.md` archive semantics so non-maintenance cycle docs can close out (latest archive: `docs/projects/archive/techdebt/OBT03062026/`). |
| protocol-governed | staged-waiting | P3-waiting | `docs/projects/protocol-governed/` | Orket Core | Runtime execution is complete and archived at `docs/projects/archive/protocol-governed/PG03062026/`; remaining reopen conditions are externally gated (real production traffic and six-month post-production evidence). Review monthly; next review `2026-04-06`. |
| future | backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred project lanes (for example `UIForge`, `NervousSystem`). |
| LieDetector | completed-archive | complete | `docs/projects/archive/LieDetector/` | Orket Core | Archived project lane; v1 completed and moved to archive. |
| SDK-2026-03-01-Audio | completed-archive | complete | `docs/projects/archive/SDK-2026-03-01-Audio/` | Orket Core | SDK typed audio capabilities, Piper/audio backend wiring, bridge integration, and reforger voice-profile validation completed in-repo. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| RuleSim-2026-03-01 | completed-archive | complete | `docs/projects/archive/RuleSim-2026-03-01/` | Orket Core | RuleSim v0 implemented; docs archived after completion. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
