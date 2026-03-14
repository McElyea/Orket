# Live Runtime Proof Recovery Plan

Last updated: 2026-03-13
Status: Archived
Owner: Orket Core
Scope anchor: runtime-stability closeout checkpoint `b739d07` (`feat: close runtime-stability lane`)
Lane type: Archived proof-recovery record

## Result

This recovery lane is complete and archived.

Closed live claims:
1. Claim A
2. Claim B
3. Claim C
4. Claim D
5. Claim F
6. Claim G

Claim E was revalidated on a fresh append-only live packet and remained red, so it was carried forward into a staged follow-on hardening lane instead of being left as fake active closeout work.

## Final Live State

1. Claim G closed live on Ollama `qwen2.5-coder:7b` with run id `c0a73c12`.
2. Fresh Claim E rerun4 used append-only ledger mode and produced run ids `6b3a2424` and `8faad44b`.
3. Strict compare for Claim E remained `deterministic_match=false`.
4. The fresh Claim E mismatch was not only run-id noise:
   - `agent_output/requirements.txt` drifted
   - `agent_output/design.txt` drifted
   - `agent_output/main.py` drifted
5. Volatile runtime artifacts also drifted:
   - `agent_output/observability/runtime_events.jsonl`
   - `agent_output/verification/runtime_verification.json`
6. A fresh non-ledger rerun3 also showed output drift, but it did not emit `events.log`; the canonical replay packet therefore uses rerun4 with `ORKET_RUN_LEDGER_MODE=append_only`.

## Carry-Forward Authority

Future hardening for Claim E now lives here:
1. `docs/projects/future/RUNTIME-STABILITY-LIVE-COMPARE-HARDENING-PLAN.md`

Canonical published proof:
1. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13.json`

## Canonical Evidence

1. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/claims.json`
2. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/result.json`
3. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/replay_outputs/claim_e_rerun4_compare.json`
4. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13/claim_e_operator_surface_diff_summary.json`

## Canonical Claim E Command Set

1. `ORKET_LIVE_ACCEPTANCE=1 ORKET_LIVE_MODEL=qwen2.5-coder:7b ORKET_RUN_LEDGER_MODE=append_only python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_e_run_a`
2. `ORKET_LIVE_ACCEPTANCE=1 ORKET_LIVE_MODEL=qwen2.5-coder:7b ORKET_RUN_LEDGER_MODE=append_only python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_e_run_b`
3. `python scripts/protocol/run_protocol_replay_compare.py --run-a-events <run_a_events> --run-b-events <run_b_events> --run-a-artifacts <run_a_artifacts> --run-b-artifacts <run_b_artifacts> --out <compare_json> --strict`

## Archive Note

This file must remain archived unless one of these becomes true:
1. shipped runtime code changes invalidate the archived proof package
2. the user asks for fresh provider/model evidence on a different live path
