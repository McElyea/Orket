# Controller Workload Externalization Template

Last updated: 2026-03-08
Status: Active
Owner: Orket Core

Source slice authority:
`docs/projects/controller-workload/05-IMPLEMENTATION-PLAN-Phase-2B.md`

## 1. Purpose

Provide a bootstrap template for moving `extensions/controller_workload` into an external extension repository without changing runtime authority semantics.

## 2. Template Path

Template files:
1. `docs/projects/controller-workload/templates/controller_workload_external/manifest.json`
2. `docs/projects/controller-workload/templates/controller_workload_external/extension.json`
3. `docs/projects/controller-workload/templates/controller_workload_external/workload_entrypoint.py`

## 3. Migration Rules

1. Keep child dispatch authority on `ExtensionManager.run_workload`.
2. Keep controller runtime semantics sourced from in-repo modules:
   - `orket.extensions.controller_dispatcher`
   - `orket.extensions.controller_observability`
3. Do not add direct child entrypoint calls in the external package.
4. Preserve stable controller error codes and fail-closed behavior.

## 4. Minimal Migration Steps

1. Create external repo skeleton from template:
   - `python scripts/extensions/bootstrap_controller_external_repo.py --target <external_repo_path>`
2. Initialize and commit the external repository (git required by extension install flow).
3. Keep `workload_id = controller_workload_v1` unless a contract version change is explicitly approved.
4. Install via normal extension path:
   - `python -m pytest -q tests/runtime/test_controller_replay_parity.py -k external_template_repo_installs_and_runs_controller_workload`
5. Validate parity behavior:
   - `python -m pytest -q tests/runtime/test_controller_replay_parity.py tests/scripts/test_compare_controller_replay_parity.py`

## 5. Fallback and Blockers

1. If external git hosting/credentials are unavailable, use local repository-path install verification as the authoritative migration preflight.
2. Production-like live verification remains a later initiative step and must be tracked separately from local-path migration proof.

## 6. Authority Boundary

This template is bootstrap guidance only.

Canonical runtime contract authority remains:
1. `docs/specs/CONTROLLER_WORKLOAD_V1.md`
2. `docs/specs/CONTROLLER_OBSERVABILITY_V1.md`
