# TD04072026B Techdebt Closeout

Last updated: 2026-04-07
Status: Completed
Owner: Orket Core

## Scope

This archive packet closes the finite techdebt remediation lane formerly tracked at `docs/projects/techdebt/action_plan.md`.

Archived lane files:
1. `action_plan.md`
2. `behavioral_review.md`
3. `code_review.md`

## Outcome

Closed all action-plan items from Sprint 1 through Sprint 4 and the architectural follow-up section:
1. P1-01 through P1-06.
2. P2-01 through P2-07.
3. P3-01 through P3-05.
4. P4-01 through P4-05.
5. A-01 through A-03.

The active `docs/projects/techdebt/` folder returns to standing-maintenance-only authority.

## Proof Summary

Proof type: unit, contract, integration, local workflow structural checks, and local helper-script smoke.

Observed path: primary.

Observed result: success.

Verified:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_runtime_verifier_service.py tests/application/test_tool_parser.py tests/scripts/test_inspect_local_runner_containers.py tests/application/test_benchmark_determinism_claims.py tests/application/test_benchmark_scoring_pipeline.py tests/platform/test_quality_workflow_gates.py tests/application/test_baseline_retention_weekly_workflow.py tests/application/test_turn_response_parser.py tests/scripts/test_check_protocol_enforce_cutover_readiness.py tests/scripts/test_ci_scripts.py tests/application/test_turn_artifact_writer.py tests/application/test_async_protocol_run_ledger.py tests/application/test_protocol_append_only_ledger.py tests/application/test_turn_tool_control_plane_support.py tests/interfaces/test_api.py tests/integration/test_system_acceptance_flow.py tests/interfaces/test_extension_runtime_api_routes.py` -> 245 passed.
2. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q @files` for all `tests/interfaces/test_api*.py` files -> 174 passed.
3. `python -m ruff check` over changed runtime, scripts, workflow tests, and interface-test helper files -> passed.
4. `ORKET_DISABLE_SANDBOX=1` helper-script smoke for memory fixture generation, migration bootstrap and validation, migration runner application, and sandbox leak gate -> passed.
5. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_ci_scripts.py tests/platform/test_quality_workflow_gates.py` -> 7 passed after fail-closed sandbox leak gate hardening.
6. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q` -> 3846 passed, 52 skipped, 9 warnings.
7. `python scripts/governance/check_docs_project_hygiene.py` -> passed.
8. `git diff --check` -> passed with line-ending normalization warnings only.

## Not Verified Here

1. No live external provider was invoked.
2. No intentional live sandbox acceptance flow was run.
3. Gitea workflows were verified structurally and by local helper-script equivalents, not by a live Gitea runner execution.

## Operational Cleanup

During sandbox leak gate verification, two pre-existing orphaned Orket-managed Docker volumes were detected, inspected as unattached to containers, and removed:
1. `orket-sandbox-productflow_exp_db-data`
2. `orket-sandbox-productflow_governed_write_file_db-data`

The sandbox leak gate passed after removing those pre-existing leaks.

## Remaining Drift

No unresolved completion-blocking drift remains for this closed lane. The active roadmap keeps the future `orket.orket` compatibility shim removal lane unchanged.
