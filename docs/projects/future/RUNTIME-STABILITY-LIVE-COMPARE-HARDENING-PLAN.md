# Runtime Stability Live Compare Hardening Plan

Last updated: 2026-03-13
Status: Staged / Waiting
Owner: Orket Core
Lane type: Staged / Waiting (explicit reopen required)

## Purpose

Own the follow-on hardening work for archived runtime-stability Claim E.

This lane exists because the live proof recovery lane is complete, but fresh provider-backed strict compare is still red on operator-visible outputs.

## Current Truth

Fresh live evidence on Ollama `qwen2.5-coder:7b`:
1. append-only rerun4 produced run ids `6b3a2424` and `8faad44b`
2. strict compare reported `deterministic_match=false`
3. operator-visible outputs drifted between the two runs:
   - `agent_output/requirements.txt`
   - `agent_output/design.txt`
   - `agent_output/main.py`
4. volatile runtime artifacts also drifted:
   - `agent_output/observability/runtime_events.jsonl`
   - `agent_output/verification/runtime_verification.json`

Canonical evidence:
1. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/replay_outputs/claim_e_rerun4_compare.json`
2. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13/claim_e_operator_surface_diff_summary.json`
3. `docs/projects/archive/runtime-stability-closeout/LIVE-RUNTIME-PROOF-RECOVERY-PLAN.md`

## Goal

Do one of these truthfully:
1. make equivalent live runs compare cleanly at the canonical operator surface
2. narrow the deterministic-compare claim/spec so Orket stops claiming determinism beyond what live proof supports

## Truth Rules

1. Do not normalize away drift in `agent_output/requirements.txt`, `agent_output/design.txt`, or `agent_output/main.py` as mere formatting noise.
2. Only normalize volatile artifacts if the operator-surface contract explicitly excludes them.
3. Mocked, provider-free, or structural-only proof does not close this lane.

## Reopen Trigger

Reopen only with an explicit request that names one of these scopes:
1. reduce live output nondeterminism
2. narrow replay compare semantics to the truthful operator surface
3. update the governing spec/contract for deterministic compare

## Canonical Command Set

1. `python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --auto-select-model --smoke-stream`
2. `ORKET_LIVE_ACCEPTANCE=1 ORKET_LIVE_MODEL=qwen2.5-coder:7b ORKET_RUN_LEDGER_MODE=append_only python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_e_run_a`
3. `ORKET_LIVE_ACCEPTANCE=1 ORKET_LIVE_MODEL=qwen2.5-coder:7b ORKET_RUN_LEDGER_MODE=append_only python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_e_run_b`
4. `python scripts/protocol/run_protocol_replay_compare.py --run-a-events <run_a_events> --run-b-events <run_b_events> --run-a-artifacts <run_a_artifacts> --run-b-artifacts <run_b_artifacts> --out <compare_json> --strict`

## Exit Artifacts

1. updated contract/spec text if deterministic compare semantics change
2. fresh live compare JSON and stdout logs
3. targeted structural tests if comparator logic changes
4. refreshed published artifact only if the new result is unusually illustrative
