# ControlPlane Workload and Run Authority Follow-On Implementation Plan
Last updated: 2026-04-09
Status: Archived implementation authority
Owner: Orket Core
Lane type: Control-plane follow-on / residual Workstream 1 closure

Archive closeout:
1. `docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/CLOSEOUT.md`

Historical context:
1. `docs/projects/archive/ControlPlane/CP04092026-CONVERGENCE-REOPEN-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_REOPEN_IMPLEMENTATION_PLAN.md`
2. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md`
3. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CLOSEOUT.md`

## Archived outcome

This bounded follow-on queue closed on `2026-04-09`.

Archived facts:
1. `Slice W1A` completed with the required governed start-path workload-authority proof set still green and no further runtime code changes required
2. `Slice W1B` completed with the required run / attempt / step projection proof set still green and no further runtime code changes required
3. `Slice W1C` completed by synchronizing the roadmap, packet docs, current-authority snapshot, and archive posture so no active ControlPlane implementation queue remains
4. the residual compatibility exits tracked by this lane, `CE-01` and `CE-02`, are closed for the governed start-path and projection-read surfaces covered by the queue

## Executed slice queue

### Slice W1A - Completed governed start-path workload authority closure on remaining entrypoints

1. Crosswalk rows: `Workload`
2. Required proof command: `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/interfaces/test_cli_startup_semantics.py tests/interfaces/test_sessions_router_protocol_replay.py`
3. Outcome: the governed start-path matrix and workload-authority governance lock remained green without further runtime code changes

### Slice W1B - Completed run / attempt / step projection demotion on residual review and runtime readbacks

1. Crosswalk rows: `Run`, `Attempt`, `Step`
2. Required proof commands:
   - `python -m pytest -q tests/runtime/test_run_identity_projection.py tests/runtime/test_run_start_artifacts.py tests/runtime/test_run_start_retry_classification_policy_immutability.py`
   - `python -m pytest -q tests/runtime/test_run_summary_projection_validation.py tests/runtime/test_run_summary.py tests/scripts/test_common_run_summary_support.py`
   - `python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py tests/scripts/test_check_1000_consistency.py`
   - `python -m pytest -q tests/runtime/test_retry_classification_policy.py tests/runtime/test_runtime_truth_drift_checker.py tests/scripts/test_check_retry_classification_policy.py tests/scripts/test_run_runtime_truth_acceptance_gate.py`
3. Outcome: the residual read surfaces remained truthfully framed as durable control-plane projection or projection-only compatibility evidence without further runtime code changes

### Slice W1C - Completed lane-wide closeout synchronization

1. Required proof commands:
   - `python scripts/governance/check_docs_project_hygiene.py`
   - `python -m pytest -q tests/platform/test_current_authority_map.py`
2. Outcome: roadmap, packet docs, current-authority snapshot, and archive posture now tell one story and no active ControlPlane implementation queue remains
