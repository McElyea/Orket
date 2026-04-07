# TD04062026D Closeout

Last updated: 2026-04-06
Status: Completed
Owner: Orket Core

## Scope

This archive packet closes the finite techdebt remediation lane formerly tracked at `docs/projects/techdebt/remediation_plan.md`.

Archived lane files:
1. `remediation_plan.md`
2. `code_review.md`
3. `behavioral_review.md`

## Outcome

Closed W1 through W4 from the remediation plan.

W5 remains deferred pending an explicit ControlPlane convergence lane reopen. W6 remains non-blocking hygiene and is not part of the completion gate.

The active `docs/projects/techdebt/` folder returns to standing-maintenance-only authority plus the live-runtime recovery plan.

## Proof Summary

Proof type: structural, contract, integration, and local workflow execution smoke.

Observed path: primary.

Observed result: success, except ShellCheck was not available in this environment.

Verified:
1. `python -m pytest -q tests/kernel/v1/test_canonical_rfc8785_backend.py tests/kernel/v1/test_odr_core.py::test_run_round_does_not_mutate_input_state tests/kernel/v1/test_spec_002_lsi_v1.py::test_stage_triplet_is_defined_directly_on_lsi_class` -> passed.
2. `python -m pytest -q tests/kernel/v1/test_odr_determinism_gate.py` -> passed.
3. `python -m pytest -q tests/scripts/test_repro_odr_gate.py` -> passed.
4. `python -m pytest -q tests/integration/test_sandbox_lifecycle_event_service.py` -> passed.
5. `python -m pytest -q tests/contracts/test_sandbox_lifecycle_mutation_contract.py tests/integration/test_sandbox_lifecycle_mutation_service.py` -> passed.
6. `python -m pytest -q tests/application/test_tool_approval_control_plane_operator_service.py tests/adapters/test_openclaw_jsonl_torture_adapter.py` -> passed.
7. `python -m pytest -q tests/application/test_run_textmystery_policy_conformance.py tests/application/test_register_textmystery_bridge_extension.py tests/application/test_textmystery_bridge_sdk_runtime.py tests/scripts/test_detect_changed_packages.py tests/platform/test_quant_sweep_workflow_gates.py` -> passed.
8. `bash -n scripts/gitea/backup_gitea.sh` -> passed.
9. `rg -n "C:/Source" scripts -g '!**/__pycache__/**' -g '!node_modules/**' -g '!.venv/**'` -> no matches.
10. `ORKET_DISABLE_SANDBOX=1 python scripts/quant/run_quant_sweep.py --model-id placeholder-model --quant-tags Q8_0 --task-bank benchmarks/results/quant/quant_sweep/smoke/task_bank.json --runs 1 --runner-template "python benchmarks/results/quant/quant_sweep/smoke/stub_quant_runner.py --task {task_file} --venue {venue} --flow {flow}" --out-dir benchmarks/results/quant/quant_sweep/smoke/reports --summary-out benchmarks/results/quant/quant_sweep/smoke/sweep_summary.json --task-limit 1 --no-sanitize-model-cache` -> passed.
11. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_driver_cli.py tests/application/test_driver_json_parse_modes.py tests/core/test_domain_deprecation_shim.py tests/integration/test_toolbox_refactor.py tests/adapters/test_tool_runtime_executor.py tests/platform/test_current_authority_map.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_turn_tool_control_plane_closeout.py tests/integration/test_turn_executor_control_plane_evidence.py` -> 62 passed.
12. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q` -> 3804 passed, 52 skipped, 5 warnings.
13. `python scripts/governance/check_docs_project_hygiene.py` -> passed.
14. `git diff --check` -> passed with line-ending normalization warnings only.

## Not Verified Here

1. ShellCheck was not run because `shellcheck` was not installed in this environment.
2. No live sandbox resource path was intentionally executed.
3. The Gitea runner was not invoked; the quant workflow execution step was verified by structural workflow checks and the local equivalent smoke command.

## Remaining Drift

No unresolved completion-blocking drift for this closed lane. Existing `orket.orket` deprecation warnings remain tracked by the future shim-removal lane in `docs/ROADMAP.md`.
