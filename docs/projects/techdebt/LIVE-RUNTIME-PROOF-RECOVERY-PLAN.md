# Live Runtime Proof Recovery Plan

Last updated: 2026-03-13
Status: Active
Owner: Orket Core
Scope anchor: runtime-stability closeout checkpoint `b739d07` (`feat: close runtime-stability lane`)
Lane type: Remaining-work tracker

## Purpose

Track only the live proof work that is still open after the 2026-03-13 provider-backed proof package.

This file is no longer the full replay of the lane. Closed claims stay closed and are referenced only through their evidence package.

## Live Definition

For this lane, `live` means:
1. a real model path through Ollama or LM Studio
2. real Orket runtime execution against a real filesystem workspace
3. fresh runtime artifacts or operator-visible outputs

These do not count:
1. mocks
2. fakes
3. shims
4. provider-patched or provider-free runs
5. unit, contract, or integration coverage without a live model path

## Closed Proof, Not Active TODO

The following claims are already closed for this lane and should not stay in the active task list unless later code changes invalidate them:

1. Claim A
   - provider-backed live acceptance run completed on Ollama `qwen2.5-coder:7b`
   - canonical run id: `17d0dacd`
2. Claim C
   - canonical `run_summary.json` and protocol `events.log` were emitted from the captured live run
3. Claim D
   - operator replay succeeded against the fresh live run with `compatibility_validation.status = ok`
4. Claim F
   - strict replay compatibility failed closed with `E_REPLAY_ARTIFACTS_MISSING` for missing `workspace_state_snapshot` fields

Canonical closed evidence:
1. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/claims.json`
2. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/result.json`
3. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13.json`

Do not rerun Claims A, C, D, or F unless:
1. shipped runtime code changes in a way that could invalidate the proof
2. the user asks for fresh evidence on a different provider/model path
3. a later fix for Claims B, E, or G requires a replacement proof package

## Current Stop Line

Only three items remain active in this lane:

1. Claim B
   - partially recovered
   - illegal state transition fails closed live
   - path traversal still drifts instead of reaching a stable fail-closed `BLOCKED` outcome
2. Claim E
   - unresolved
   - strict compare across two fresh live runs reported `deterministic_match=false`
3. Claim G
   - blocked
   - protocol-governed acceptance still fails before tool execution with `E_MARKDOWN_FENCE`

If Orket Core accepts the current drift/blocker classifications as the final outcome for this cycle, archive this file and remove the roadmap item instead of widening this lane.

## Remaining Claim B

Goal:
1. restore a stable live fail-closed result for path traversal boundary violations

Current observed live drift:
1. one live rerun emitted a governance violation report but left `ISSUE-B` in `in_progress` via retry
2. another live rerun corrected `../secret.txt` to workspace-relative `secret.txt` and completed the write

Canonical evidence:
1. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/pytest_tmp_claim_b_rerun2/test_boundary_path_traversal_l0/workspace/agent_output/policy_violation_ISSUE-B.json`
2. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/pytest_tmp_claim_b_rerun3/test_boundary_path_traversal_l0/workspace/orket.log`
3. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/stdout_claim_b_rerun2.log`
4. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/stdout_claim_b_rerun3.log`

Canonical command:
1. `python -m pytest tests/live/test_runtime_stability_closeout_live.py::test_boundary_illegal_state_transition_live tests/live/test_runtime_stability_closeout_live.py::test_boundary_path_traversal_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_b`

Exit criteria:
1. the path traversal live node ends fail closed every run
2. `ISSUE-B` ends `BLOCKED`
3. no sanitized `secret.txt` write is materialized from the traversal attempt
4. the violation artifact remains present and truthful

Closeout update when done:
1. refresh `claims.json` and `result.json` in the proof root
2. remove Claim B from this active file
3. add a published artifact only if the new live result is benchmark-worthy

## Remaining Claim E

Goal:
1. determine whether strict compare can truthfully be made green for equivalent fresh live runs

Current observed live drift:
1. strict compare across live runs `17d0dacd` and `d5e64e56` reported `deterministic_match=false`

Canonical evidence:
1. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/replay_outputs/claim_e_script_compare.json`
2. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/stdout_claim_e_cli_compare.log`
3. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/stderr_claim_e_cli_compare.log`

Canonical command set:
1. `python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_e_run_a`
2. `python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_e_run_b`
3. `python scripts/protocol/run_protocol_replay_compare.py --run-a-events <run_a_events> --run-b-events <run_b_events> --run-a-artifacts <run_a_artifacts> --run-b-artifacts <run_b_artifacts> --strict`

Exit criteria:
1. either strict compare returns `deterministic_match=true` on fresh equivalent runs
2. or the remaining mismatch is explicitly split into a separate runtime hardening lane and this recovery lane is archived without pretending compare is green

Closeout update when done:
1. refresh `claims.json` and `result.json` in the proof root
2. remove Claim E from this active file
3. publish only if the final compare result is unusually illustrative

## Remaining Claim G

Goal:
1. obtain one provider-backed protocol-governed live run that reaches tool execution and emits manifest-inspection evidence

Current blocker:
1. the exercised protocol-governed acceptance path fails before tool execution with `E_MARKDOWN_FENCE`

Canonical evidence:
1. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/pytest_tmp_claim_g/test_system_acceptance_role_pi0/workspace/orket.log`
2. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/pytest_tmp_claim_g/test_system_acceptance_role_pi0/workspace/agent_output/policy_violation_REQ-1.json`
3. `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/stdout_claim_g.log`

Canonical command:
1. `python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_g`

Required env:
1. `ORKET_LIVE_ACCEPTANCE=1`
2. `ORKET_LIVE_MODEL=<model>`
3. `ORKET_RUN_LEDGER_MODE=protocol`
4. `ORKET_PROTOCOL_GOVERNED_ENABLED=1`
5. `ORKET_LOCAL_PROMPTING_MODE=enforce`

Exit criteria:
1. the governed live run reaches tool execution instead of failing in envelope parsing
2. fresh `receipts.log` or equivalent tool-level protocol events exist
3. `tool_invocation_manifest` exposes only the narrowed SPC-06 fields:
   - `tool_name`
   - `ring`
   - `schema_version`
   - `determinism_class`
   - `capability_profile`
   - `tool_contract_version`
4. richer registry metadata is absent:
   - `input_schema`
   - `output_schema`
   - `error_schema`
   - `side_effect_class`
   - `timeout`
   - `retry_policy`

Closeout update when done:
1. refresh `claims.json` and `result.json` in the proof root
2. remove Claim G from this active file
3. publish only if the manifest evidence is clean and representative

## Execution Order

Run remaining work in this order:
1. Claim B
2. Claim G
3. Claim E

Rationale:
1. Claim B is the highest-severity fail-closed boundary drift
2. Claim G is the remaining manifest-surface blocker
3. Claim E is still important, but compare truth should be evaluated after any runtime changes made for the more severe open claims

## Archive Trigger

Archive this file and remove the roadmap entry when one of these becomes true:
1. Claims B, E, and G are all closed with fresh live evidence
2. Orket Core explicitly accepts the current Claim B/E/G drift-blocker set as the final truthful outcome for this cycle and tracks any follow-on hardening in a separate lane

Archive steps:
1. move this file under `docs/projects/archive/runtime-stability-closeout/`
2. keep the canonical proof root under `benchmarks/results/techdebt/live_runtime_proof/2026-03-13_live-proof_runtime-stability-qwen2.5-coder-7b/`
3. keep the published artifact if it still reflects the final truthful state
4. update `docs/ROADMAP.md`
5. run `python scripts/governance/check_docs_project_hygiene.py` if roadmap or `docs/projects/` structure changed
