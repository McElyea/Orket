# Orket Roadmap

Last updated: 2026-04-01

Workflow authority: `docs/CONTRIBUTOR.md`

## Priority Now

1. None.

## Maintenance (Non-Priority)

1. techdebt -- Standing recurring maintenance. Checklist: `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`. Governance: `docs/projects/techdebt/README.md`.

## Paused / Checkpointed Lanes

1. ControlPlane convergence -- Paused after a truthful partial-convergence checkpoint. Authority: `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`. Reopen only for authority drift bugs, proof failures, same-change doc sync required by touched runtime slices, or an explicitly reopened convergence packet or roadmap lane.

## Staged / Waiting (Externally Gated)

1. protocol-governed production-window operator sign-off -- Contract: `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`. Archive: `docs/projects/archive/protocol-governed/PG03062026/`. Next review: `2026-04-06`.
2. protocol-governed post-production six-month evidence -- Contract: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Next review: `2026-04-06`.

## Future Lanes (Non-Priority Backlog)

1. protocol-governed local provider compatibility expansion (`vLLM`, `llama.cpp`) -- Contract: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Readiness: `benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json` (`ready=true` for current admitted profiles). Reopen only with an explicit scoped implementation request.
2. marshaller requirements hardening -- Hold until requirements are mature and explicitly approved for execution.

## Project Index

Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| ControlPlane | paused-checkpoint | paused | `docs/projects/ControlPlane/` | Orket Core | Control-plane packet requirements remain active scoped requirements authority; `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md` is the paused partial-convergence checkpoint and explicit-reopen authority; reopen only for authority drift bugs, proof failures, same-change doc sync required by touched runtime slices, or an explicitly reopened convergence packet or roadmap lane; prior packet-v2 implementation lane remains archived at `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md` with closeout in `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/CLOSEOUT.md`. |
| marshaller | future-hold | P3-scaffolding | `docs/projects/marshaller/` | Orket Core | Scaffolding-only; keep parked until requirements hardening is explicitly approved. |
| techdebt | maintenance only | P2-maintenance | `docs/projects/techdebt/` | Orket Core | Standing maintenance continues through `Recurring-Maintenance-Checklist.md` and `README.md`. |
| future | staged+backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred lanes that are not yet part of an active non-archive project lane. |
