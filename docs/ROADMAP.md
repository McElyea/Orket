# Orket Roadmap

Last updated: 2026-04-25

Workflow authority: `docs/CONTRIBUTOR.md`

## Priority Now

No active priority items.

## Maintenance (Non-Priority)

1. techdebt recurring maintenance -- authorities: `docs/projects/techdebt/README.md`, `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`, and `docs/projects/techdebt/LIVE-RUNTIME-PROOF-RECOVERY-PLAN.md`.

## Paused / Checkpointed Lanes

1. NorthStar disposable AWS smoke setup lane -- Paused pending Bedrock access. Authority: `docs/projects/northstar-aws-smoke-setup/NORTHSTAR_AWS_SMOKE_SETUP_IMPLEMENTATION_PLAN.md`. Reopen only when Bedrock access is available and the user explicitly requests live completion or reopen.
1. NorthStar second governed change packet family admission lane -- Paused after the truthful 2026-04-20 Terraform public-admission checkpoint. Authority: `docs/projects/northstar-governed-change-packets/ORKET_NORTHSTAR_SECOND_GOVERNED_CHANGE_PACKET_FAMILY_IMPLEMENTATION_PLAN.md`. Reopen only when a bounded change can truthfully provide the required non-secret live inputs `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI`, `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID`, and `AWS_REGION` or `AWS_DEFAULT_REGION`, rerun the full Workstream 2 proof envelope, and re-evaluate the publication-readiness and publication-gate outputs in the same change, or when the lane is explicitly reopened for retirement.
1. governed-proof strategic lane -- Paused after the truthful 2026-04-19 provider-backed Bedrock checkpoint. Authority: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`. Reopen only when a bounded change can run the admitted provider-backed governed-proof path with non-zero Bedrock inference quota, or when the lane is explicitly reopened for retirement.
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
| northstar-aws-smoke-setup | paused-checkpoint | paused | `docs/projects/northstar-aws-smoke-setup/` | Orket Core | Paused pending Bedrock access. No-spend setup, randomized fixtures, and blocked handoff are implemented; reopen only when Bedrock access is available and the user explicitly requests live completion or reopen. This lane does not publicly admit `trusted_terraform_plan_decision_v1`. |
| governed-proof | paused-checkpoint | paused | `docs/projects/governed-proof/` | Orket Core | Paused after the truthful 2026-04-19 provider-backed Bedrock checkpoint. `ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md` remains the canonical pause and reopen authority; reopen only when a bounded change can use an AWS account or Region with non-zero Bedrock inference quota for the admitted provider-backed governed-proof path, or for explicit retirement. |
| northstar-governed-change-packets | paused-checkpoint | paused | `docs/projects/northstar-governed-change-packets/` | Orket Core | Paused after the truthful 2026-04-20 Terraform public-admission checkpoint. `ORKET_NORTHSTAR_SECOND_GOVERNED_CHANGE_PACKET_FAMILY_IMPLEMENTATION_PLAN.md` remains the canonical pause and reopen authority; reopen only when a bounded change can truthfully provide the required non-secret live inputs, rerun the full Workstream 2 proof envelope, and re-evaluate the publication-readiness and publication-gate outputs in the same change, or for explicit retirement. |
| marshaller | future-hold | P3-scaffolding | `docs/projects/marshaller/` | Orket Core | Scaffolding-only; keep parked until requirements hardening is explicitly approved. |
| OrketUI | shipped-reference | reference | `docs/projects/OrketUI/` | Orket Core | Shipped Orket-side provenance packet for the separate OrketUI extension. The completed lane record lives under `docs/projects/archive/OrketUI/OUI04092026-LANE-CLOSEOUT/`; future OrketUI expansion must reopen as a new explicit roadmap lane. |
| PromptReforgerToolCompatibility | paused-checkpoint | paused | `docs/projects/PromptReforgerToolCompatibility/` | Orket Core | Paused after the truthful 2026-04-04 portability checkpoint. `PROMPT_REFORGER_GEMMA_TOOL_USE_IMPLEMENTATION_PLAN.md` remains the canonical pause and reopen authority; the FunctionGemma judge blocker is now cleared through the admitted native-tool path, keep Prompt Reforger service truth in `docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md`, keep Gemma 4 deferred, and keep Qwen out of the core lane unless a later explicit cross-family baseline is requested. |
| techdebt | standing-maintenance | maintenance | `docs/projects/techdebt/` | Orket Core | Standing recurring maintenance remains under `Recurring-Maintenance-Checklist.md`, `LIVE-RUNTIME-PROOF-RECOVERY-PLAN.md`, and `README.md`; completed cycle archives live under `docs/projects/archive/techdebt/`. |
| future | staged+backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred lanes that are not yet part of an active non-archive project lane; active nested lanes are indexed separately. |
