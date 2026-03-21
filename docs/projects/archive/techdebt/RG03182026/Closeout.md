# RG03182026 Closeout

Last updated: 2026-03-18
Status: Archived
Owner: Orket Core

## Scope

This cycle closed the bounded Phase 1 runtime gaps without widening into a general orchestrator rewrite.

Primary closure areas:
1. explicit cards execution profiles and artifact-contract routing
2. canonical cards `stop_reason` reporting
3. ODR semantic-validity hardening plus a governed five-run live baseline
4. explicit ODR/cards prebuild integration with direct observability
5. active-doc cleanup and archive handoff

## Completion Gate Outcome

The conclusive gate defined in [docs/projects/archive/techdebt/RG03182026/01-REQUIREMENTS.md](docs/projects/archive/techdebt/RG03182026/01-REQUIREMENTS.md) is satisfied:

1. `builder_guard_app_v1` is explicit in cards runtime artifacts.
2. `builder_guard_artifact_v1` exists and passed live P-01 and P-03 artifact-path proof.
3. Cards run summary now emits canonical `stop_reason`.
4. The five-run live ODR baseline returned governed stop reasons only, with `UNRESOLVED_DECISIONS` in all five runs, one raw signature, and no unexpected hard `CODE_LEAK` or repeated format failure.
5. The explicit ODR/cards path `odr_prebuild_builder_guard_v1` emits direct ODR artifacts plus `odr_active`, `odr_valid`, `odr_pending_decisions`, `odr_stop_reason`, and `odr_artifact_path`.
6. Non-ODR cards runs emit `odr_active=false`.
7. `python scripts/governance/check_docs_project_hygiene.py` passes.

## Verification

Live proof:
1. `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --smoke-stream` -> `PASS`
2. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p01_single_issue.py --workspace .probe_workspace_p01_app_final --execution-profile builder_guard_app_v1 --artifact-path agent_output/main.py --model qwen2.5-coder:7b --json` -> `observed_result=success`, `execution_profile=builder_guard_app_v1`, `stop_reason=completed`, wrote `agent_output/main.py`
3. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p01_single_issue.py --workspace .probe_workspace_p01_artifact_final --execution-profile builder_guard_artifact_v1 --artifact-path agent_output/fibonacci.py --model qwen2.5-coder:7b --json` -> `observed_result=success`, `execution_profile=builder_guard_artifact_v1`, `stop_reason=completed`, wrote `agent_output/fibonacci.py`
4. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p03_epic_trace.py --workspace .probe_workspace_p03_closeout --execution-profile builder_guard_artifact_v1 --model qwen2.5-coder:7b --json` -> `observed_result=success`, `stop_reason=completed`, produced `agent_output/schema.json`, `agent_output/writer.py`, and `agent_output/reader.py`
5. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p02_odr_isolation.py --model qwen2.5-coder:7b --runs 5 --json` -> `observed_result=success`, `stop_reason_distribution={"UNRESOLVED_DECISIONS": 5}`, `unique_raw_signatures=1`, `determinism=STABLE`
6. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p04_odr_cards_integration.py --workspace .probe_workspace_p04_live --model qwen2.5-coder:7b --json` -> `observed_result=success`; non-ODR run emitted `odr_active=false`, and ODR-enabled run emitted direct ODR artifact and summary fields under `odr_prebuild_builder_guard_v1`
7. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p04_odr_cards_integration.py --workspace .probe_workspace_p04_live_max_rounds_proven --model qwen2.5-coder:7b --output benchmarks/results/probes/p04_odr_cards_integration_max_rounds_proven.json --json` -> `observed_result=success`; the ODR-enabled run ended `status=done` / `stop_reason=completed` after `odr_stop_reason=MAX_ROUNDS` with `odr_valid=true`, `odr_pending_decisions=0`, and ODR artifact `accepted=true`

Structural proof:
1. `python -m pytest tests/adapters/test_async_card_repository.py -q` -> `16 passed`
2. `python -m pytest tests/kernel/v1/test_odr_core.py -q` -> `11 passed`
3. `python -m pytest tests/core/test_cards_runtime_contract.py -q` -> `2 passed`
4. `python -m pytest tests/runtime/test_run_summary.py -q` -> `4 passed`
5. `python -m pytest tests/kernel/v1/test_odr_refinement_behavior.py -q` -> `16 passed, 2 skipped`
6. `python -m pytest tests/kernel/v1/test_odr_leak_policy_balanced.py -q` -> `31 passed`
7. `python -m pytest tests/kernel/v1/test_odr_determinism_gate.py -q` -> `3 passed, 1 skipped`
8. `python -m pytest tests/application/test_turn_message_builder.py -q` -> `3 passed`
9. `python -m pytest tests/application/test_orchestrator_epic.py -q` -> `52 passed`
10. `python -m pytest tests/application/test_execution_pipeline_run_ledger.py -q` -> `14 passed`

Governance proof:
1. `python scripts/governance/check_docs_project_hygiene.py` -> `passed`

## Post-Closeout Clarification

1. Accepted `MAX_ROUNDS` continuation is now proven for `odr_prebuild_builder_guard_v1`: the prebuild may continue when `odr_valid=true`, `odr_pending_decisions=0`, and `odr_accepted=true`, while preserving the truthful ODR stop reason `MAX_ROUNDS`.
2. The prebuild acceptance rule is semantic-validity- and decision-completeness-based. Auditor `REWRITE` patches are advisory unless they surface governed semantic invalidity, unresolved required decisions, contradiction, required-constraint regression, or another explicit blocking signal.
3. Non-accepted ODR outcomes remain fail-closed.

## Not Fully Verified

1. This archive does not claim that every non-accepted ODR outcome should continue. The proven boundary is narrower: accepted `MAX_ROUNDS` outcomes can continue; non-accepted outcomes remain fail-closed.
2. No broader Phase 2 auditability workload was executed as part of this bounded runtime-gap lane.

## Archived Documents

1. [docs/projects/archive/techdebt/RG03182026/01-REQUIREMENTS.md](docs/projects/archive/techdebt/RG03182026/01-REQUIREMENTS.md)
2. [docs/projects/archive/techdebt/RG03182026/02-IMPLEMENTATION-PLAN.md](docs/projects/archive/techdebt/RG03182026/02-IMPLEMENTATION-PLAN.md)

## Residual Risk

1. `odr_prebuild_builder_guard_v1` should remain a non-default path. Accepted `MAX_ROUNDS` continuation is now proven; the remaining contract boundary is that non-accepted ODR outcomes still fail closed.
2. Future workload claims should use the remediated cards and ODR surfaces, not the original Phase 1 snapshot, as the current baseline.
