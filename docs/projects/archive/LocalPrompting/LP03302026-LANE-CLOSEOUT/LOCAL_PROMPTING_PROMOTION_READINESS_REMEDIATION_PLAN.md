# Local Prompting Promotion Readiness Remediation Plan

Last updated: 2026-03-30
Status: Archived closeout record
Owner: Orket Core
Lane type: Maintenance-triggered remediation / closed implementation lane

Contract authority: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
Maintenance trigger: `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`

## Authority posture

This archived packet records the scoped remediation lane that was opened on 2026-03-30 after recurring maintenance Section C returned a false-red promotion-readiness result.

The lane did not reopen provider implementation or contract work.
It resolved an authority-drift problem in how Section C selected its evidence inputs.

## Source authorities

This remediation lane was bounded by:
1. `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
2. `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`
3. `docs/ROADMAP.md`
4. `CURRENT_AUTHORITY.md`
5. `benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json`
6. the current live-verification artifact roots used for drift and template-audit gates:
   1. `benchmarks/results/protocol/local_prompting/live_verification/drift/profile_delta_report.json`
   2. `benchmarks/results/protocol/local_prompting/live_verification/template_audit/`
7. the existing promotion-evidence roots for the admitted active profiles:
   1. `benchmarks/results/protocol/local_prompting/ollama_promotion_2026-03-06/conformance/ollama/ollama.qwen.chatml.v1/`
   2. `benchmarks/results/protocol/local_prompting/lmstudio_cache_study/none/promotion/conformance/openai_compat/openai_compat.qwen.openai_messages.v1/`
8. the archived protocol-governed local-prompting lane only as historical context:
   1. `docs/projects/archive/protocol-governed/PG03062026/local-prompting-plan.md`
   2. `docs/projects/archive/protocol-governed/PG03062026/implementation-plan.md`

## Classified cause

The red Section C result was caused by stale evidence selection, not by a newly proven contract regression.

Observed facts:
1. `scripts/protocol/check_local_prompting_promotion_readiness.py` was functioning correctly.
2. The red run used `live_verification/conformance/...` roots that contain only two-case live-verification spot checks.
3. Promotion-readiness gate `G2_promotion_suite_volume` requires promotion-suite evidence at `1000/500` case volume.
4. Existing promotion evidence for both admitted active profiles already existed on disk and still satisfied the contract thresholds.

Profile classifications:
1. `ollama.qwen.chatml.v1`: stale evidence selection / false red.
   The live-verification root produced smoke-sized failures, but the promotion root remained green with `strict_total=1000`, `tool_total=500`, and `failure_total=0`.
2. `openai_compat.qwen.openai_messages.v1`: stale evidence selection / false red.
   The live-verification root failed only promotion volume, but the promotion root remained green with `strict_total=1000` and `tool_total=500`.

## Remediation decision

The lane accepted the smallest truthful remediation:
1. keep the admitted active profile set unchanged
2. keep the local-prompting contract and thresholds unchanged
3. restore Section C to the actual promotion-evidence roots for the admitted active profiles
4. regenerate the canonical readiness output at `benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json`
5. close the lane without runtime, schema, or provider-implementation changes

## Closure truth

As of 2026-03-30, the canonical readiness output is green:
1. `benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json`
2. `ready=true`
3. `ollama.qwen.chatml.v1 ready=true`
4. `openai_compat.qwen.openai_messages.v1 ready=true`
5. drift remains green with `changed=false`

## Closure proof commands

1. `python scripts/protocol/check_local_prompting_promotion_readiness.py --profile-root benchmarks/results/protocol/local_prompting/ollama_promotion_2026-03-06/conformance/ollama/ollama.qwen.chatml.v1 --profile-root benchmarks/results/protocol/local_prompting/lmstudio_cache_study/none/promotion/conformance/openai_compat/openai_compat.qwen.openai_messages.v1 --drift-report benchmarks/results/protocol/local_prompting/live_verification/drift/profile_delta_report.json --template-audit-root benchmarks/results/protocol/local_prompting/live_verification/template_audit --out benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json --strict`
2. `python scripts/governance/check_docs_project_hygiene.py`

## Closure reason

This lane closed because the canonical readiness command returned `ready=true` for the admitted active profiles once Section C was pointed at the correct promotion-evidence roots.
