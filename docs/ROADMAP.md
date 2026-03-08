# Orket Roadmap

Last updated: 2026-03-08

## Operating Rule
Use `docs/CONTRIBUTOR.md` for contributor workflow and roadmap-selection rules. This file stays focused on active lane status and execution order. `Priority Now` empty means there is no priority lane; it does not mean there is no work. Active items under `Maintenance (Non-Priority)` remain executable when no priority lane exists. Standing recurring maintenance stays active but is a fallback lane and should be listed last within the section unless it is the only active maintenance work.

## Priority Now
Intentionally empty.

## Maintenance (Non-Priority)
These items are active executable work. They are non-priority, not deferred.

1. techdebt -- Standing recurring maintenance only. Source: `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`. Folder governance: `docs/projects/techdebt/README.md`. Latest evidence: `tests/reports/techdebt_recurring_cycle_2026-03-07_a_report.json`. Latest completed finite cycle archive: `docs/projects/archive/techdebt/CB03072026/Closeout.md`.

## Staged / Waiting (Externally Gated)
1. protocol-governed production-window operator sign-off -- Runtime contract: `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`. Implementation archive: `docs/projects/archive/protocol-governed/PG03062026/`. Next review `2026-04-06`.
2. protocol-governed post-production six-month evidence -- Local provider compatibility contract: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Next review `2026-04-06`.

## Future Lanes (Non-Priority Backlog)
1. protocol-governed local provider compatibility expansion (`vLLM`, `llama.cpp`) -- Contract source: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Reopen only with an explicit scoped implementation request. Readiness evidence: `benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json` (`ready=false`).
2. NervousSystem next-phase planning -- Hold until production rollout timing is explicitly scheduled.
3. marshaller requirements hardening -- Hold until requirements are mature and explicitly approved for execution.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| marshaller | future-hold | P3-scaffolding | `docs/projects/marshaller/` | Orket Core | Scaffolding-only; keep parked until requirements hardening is explicitly approved. |
| techdebt | maintenance | P3-maintenance | `docs/projects/techdebt/` | Orket Core | Standing maintenance lane. Source: `Recurring-Maintenance-Checklist.md`. Folder governance: `README.md`. |
| future | backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred project lanes (for example `UIForge`, `NervousSystem`). |
