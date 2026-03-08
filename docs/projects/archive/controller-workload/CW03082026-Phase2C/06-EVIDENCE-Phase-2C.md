# Controller Workload Phase 2C Evidence Report

Last updated: 2026-03-08
Status: Completed
Owner: Orket Core
Phase authority:
`docs/projects/archive/controller-workload/CW03082026-Phase2C/05-IMPLEMENTATION-PLAN-Phase-2C.md`

## 1. Verification Commands

Executed commands:
1. `python -m pytest -q tests/runtime/test_controller_replay_parity.py tests/scripts/test_bootstrap_controller_external_repo.py tests/scripts/test_compare_controller_replay_parity.py tests/runtime/test_controller_observability.py tests/sdk/test_controller.py`
2. `python -m py_compile extensions/controller_workload/workload_entrypoint.py docs/projects/controller-workload/templates/controller_workload_external/workload_entrypoint.py scripts/extensions/bootstrap_controller_external_repo.py`
3. `python scripts/governance/check_docs_project_hygiene.py`

Observed outcomes:
1. targeted test matrix passed
2. compile checks passed
3. docs hygiene check passed

## 2. Step 17 Evidence (External Install Migration)

Delivered migration utility:
1. `scripts/extensions/bootstrap_controller_external_repo.py`

Delivered integration proof:
1. `tests/runtime/test_controller_replay_parity.py::test_external_template_repo_installs_and_runs_controller_workload`
2. observed path/result:
   - path: `primary`
   - result: `success`
   - runtime path: installed external-style repository through `ExtensionManager.run_workload`

## 3. Step 18 Evidence (Migration Guidance)

Published guidance:
1. `docs/projects/controller-workload/06-EXTERNALIZATION-TEMPLATE.md`

Guidance includes:
1. bootstrap command flow
2. install/parity validation commands
3. fallback and blocker handling notes

## 4. Step 19 Evidence (Rollout Controls)

Implemented controls:
1. `ORKET_CONTROLLER_ENABLED`
2. `ORKET_CONTROLLER_ALLOWED_DEPARTMENTS`

Behavioral proof:
1. `tests/runtime/test_controller_observability.py::test_controller_workload_enablement_policy_blocks_run`
2. observed path/result under disablement:
   - path: `blocked`
   - result: `blocked`
   - error: `controller.disabled_by_policy`

## 5. Step 20 Evidence (Live External-Style Integration Verification)

Live verification path:
1. real end-to-end integration run through installed external-style repo path in test environment
2. command-driven execution via pytest integration case above

Observed result:
1. success
2. no contract drift in controller summary/observability outputs for migration path
