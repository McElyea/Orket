# Orket Roadmap

Last updated: 2026-03-12

Workflow authority: `docs/CONTRIBUTOR.md`

## Priority Now

## Maintenance (Non-Priority)

1. techdebt -- Standing recurring maintenance. Checklist: `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`. Governance: `docs/projects/techdebt/README.md`.

## Staged / Waiting (Externally Gated)

1. truthful runtime hardening continuation (Phases C-E) -- Plan: `docs/projects/future/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`. Archived proof: Phase A, Phase B, Wave 2 (`2026-03-10`). Reopen only with explicit proof-backed scope.
2. controller-workload v1 kickoff -- Planning handoff: `docs/projects/archive/controller-workload/CW03082026-Phase2D/07-V1-PLANNING-HANDOFF.md`. Reopen only with an explicit scoped implementation request.
3. protocol-governed production-window operator sign-off -- Contract: `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`. Archive: `docs/projects/archive/protocol-governed/PG03062026/`. Next review: `2026-04-06`.
4. protocol-governed post-production six-month evidence -- Contract: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Next review: `2026-04-06`.

## Future Lanes (Non-Priority Backlog)

1. protocol-governed local provider compatibility expansion (`vLLM`, `llama.cpp`) -- Contract: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Readiness: `benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json` (`ready=false`). Reopen only with an explicit scoped implementation request.
2. NervousSystem next-phase planning -- Hold until production rollout timing is explicitly scheduled.
3. marshaller requirements hardening -- Hold until requirements are mature and explicitly approved for execution.

## Project Index

Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| marshaller | future-hold | P3-scaffolding | `docs/projects/marshaller/` | Orket Core | Scaffolding-only; keep parked until requirements hardening is explicitly approved. |
| techdebt | maintenance | P3-maintenance | `docs/projects/techdebt/` | Orket Core | Standing maintenance lane. Checklist: `Recurring-Maintenance-Checklist.md`. Governance: `README.md`. |
| future | staged+backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred lanes; truthful runtime hardening continuation (Phases C-E) is staged pending new proof-backed execution. |
