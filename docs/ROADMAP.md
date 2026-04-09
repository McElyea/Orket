# Orket Roadmap

Last updated: 2026-04-08

Workflow authority: `docs/CONTRIBUTOR.md`

## Priority Now

1. None.

## Maintenance (Non-Priority)

1. techdebt recurring maintenance -- authorities: `docs/projects/techdebt/README.md`, `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`, and `docs/projects/techdebt/LIVE-RUNTIME-PROOF-RECOVERY-PLAN.md`.

## Paused / Checkpointed Lanes

1. Prompt Reforger Gemma tool-use lane -- Paused after the truthful 2026-04-04 portability checkpoint. Authority: `docs/projects/PromptReforgerToolCompatibility/PROMPT_REFORGER_GEMMA_TOOL_USE_IMPLEMENTATION_PLAN.md`. Reopen only for a bounded change set that clears the frozen portability corpus, with same-change rerun of the canonical inventory, cycle, and judge artifacts.

## Staged / Waiting (Externally Gated)

1. protocol-governed production-window operator sign-off -- Contract: `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`. Archive: `docs/projects/archive/protocol-governed/PG03062026/`. Next review: `2026-04-06`.
2. protocol-governed post-production six-month evidence -- Contract: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Next review: `2026-04-06`.

## Future Lanes (Non-Priority Backlog)

1. protocol-governed local provider compatibility expansion (`vLLM`, `llama.cpp`) -- Contract: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`. Readiness must be regenerated with `scripts/protocol/check_local_prompting_promotion_readiness.py` before reopen; do not treat local ignored `benchmarks/results/...` output as durable roadmap authority. Reopen only with an explicit scoped implementation request.
2. marshaller requirements hardening -- Hold until requirements are mature and explicitly approved for execution.
3. `orket.orket` compatibility shim removal -- Remove the deprecated shim after one techdebt cycle once production imports use `orket.runtime` directly.

## Project Index

Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| ControlPlane | packet-active | reference-only | `docs/projects/ControlPlane/` | Orket Core | The accepted control-plane packet and current-state crosswalk remain active requirements authority under `docs/projects/ControlPlane/orket_control_plane_packet/`; the bounded convergence lane completed on `2026-04-08` and is archived at `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/`, and the earlier packet-v2 implementation lane remains archived at `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/`; future ControlPlane implementation work must reopen explicitly through `docs/ROADMAP.md`. |
| marshaller | future-hold | P3-scaffolding | `docs/projects/marshaller/` | Orket Core | Scaffolding-only; keep parked until requirements hardening is explicitly approved. |
| PromptReforgerToolCompatibility | paused-checkpoint | paused | `docs/projects/PromptReforgerToolCompatibility/` | Orket Core | Paused after the truthful 2026-04-04 portability checkpoint. `PROMPT_REFORGER_GEMMA_TOOL_USE_IMPLEMENTATION_PLAN.md` remains the canonical pause and reopen authority; the FunctionGemma judge blocker is now cleared through the admitted native-tool path, keep Prompt Reforger service truth in `docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md`, keep Gemma 4 deferred, and keep Qwen out of the core lane unless a later explicit cross-family baseline is requested. |
| techdebt | standing-maintenance | maintenance | `docs/projects/techdebt/` | Orket Core | Standing recurring maintenance remains under `Recurring-Maintenance-Checklist.md`, `LIVE-RUNTIME-PROOF-RECOVERY-PLAN.md`, and `README.md`; completed cycle archives live under `docs/projects/archive/techdebt/`. |
| future | staged+backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred lanes that are not yet part of an active non-archive project lane. |
