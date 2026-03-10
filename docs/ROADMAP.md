# Orket Roadmap

Last updated: 2026-03-09

## Operating Rule
Use `docs/CONTRIBUTOR.md` for contributor workflow and roadmap-selection rules. This file stays focused on active lane status and execution order. `Priority Now` empty means there is no priority lane; it does not mean there is no work. Active items under `Maintenance (Non-Priority)` remain executable when no priority lane exists. Standing recurring maintenance stays active but is a fallback lane and should be listed last within the section unless it is the only active maintenance work.
Active lane entries should link the canonical implementation plan path only; requirement docs are project-local authority inputs, not the roadmap execution pointer.
Phase closeout is not initiative closeout: if a lane's initiative mini-roadmap still has pending phases, keep the lane active and archive only completed phase docs.

## Priority Now
1. truthful runtime hardening lane -- Canonical implementation plan: `docs/projects/future/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`. Wave 2 extension: `docs/projects/future/ORKET-TRUTHFUL-RUNTIME-HARDENING-WAVE-2-IMPLEMENTATION-PLAN.md`. Focus: capability truth, provenance, deterministic routing contracts, and evidence-gated promotion.

## Maintenance (Non-Priority)
These items are active executable work. They are non-priority, not deferred.

1. techdebt -- Standing recurring maintenance only. Source: `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`. Folder governance: `docs/projects/techdebt/README.md`.

## Staged / Waiting (Externally Gated)
1. controller-workload v1 kickoff -- Planning handoff: `docs/projects/archive/controller-workload/CW03082026-Phase2D/07-V1-PLANNING-HANDOFF.md`. Reopen only with an explicit scoped implementation request.
2. protocol-governed production-window operator sign-off -- Runtime contract: `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`. Implementation archive: `docs/projects/archive/protocol-governed/PG03062026/`. Next review `2026-04-06`.
3. protocol-governed post-production six-month evidence -- Local provider compatibility contract: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Next review `2026-04-06`.

## Future Lanes (Non-Priority Backlog)
1. Companion avatar post-MVP lane -- Canonical implementation plan: `docs/projects/Companion/01-AVATAR-POST-MVP-CANONICAL-IMPLEMENTATION-PLAN.md`. Contract authority: `docs/specs/COMPANION_AVATAR_POST_MVP_CONTRACT.md`.
2. protocol-governed local provider compatibility expansion (`vLLM`, `llama.cpp`) -- Contract source: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Reopen only with an explicit scoped implementation request. Readiness evidence: `benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json` (`ready=false`).
3. NervousSystem next-phase planning -- Hold until production rollout timing is explicitly scheduled.
4. marshaller requirements hardening -- Hold until requirements are mature and explicitly approved for execution.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| Companion | future-hold | P3-backlog | `docs/projects/Companion/` | Orket Core | Avatar post-MVP implementation plan set drafted; lane remains future-hold until execution kickoff. |
| marshaller | future-hold | P3-scaffolding | `docs/projects/marshaller/` | Orket Core | Scaffolding-only; keep parked until requirements hardening is explicitly approved. |
| techdebt | maintenance | P3-maintenance | `docs/projects/techdebt/` | Orket Core | Standing maintenance lane. Source: `Recurring-Maintenance-Checklist.md`. Folder governance: `README.md`. |
| future | backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred project lanes (for example `UIForge`, `NervousSystem`, truthful runtime hardening). |
