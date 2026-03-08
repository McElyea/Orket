# Controller Workload Reliability Hardening Report (Phase 2D)

Last updated: 2026-03-08
Status: Active
Owner: Orket Core
Phase authority:
`docs/projects/controller-workload/05-IMPLEMENTATION-PLAN-Phase-2D.md`

## 1. Scope

Reliability hardening pass for controller runtime surfaces implemented through Phase 2C:
1. dispatcher + observability runtime behavior
2. replay/parity comparator and scripts
3. external install-path migration utility and integration path

## 2. Reliability Verification Pass

Command executed 5 consecutive times:
1. `python -m pytest -q tests/runtime/test_controller_observability.py tests/runtime/test_controller_replay_parity.py tests/scripts/test_bootstrap_controller_external_repo.py tests/scripts/test_compare_controller_replay_parity.py tests/sdk/test_controller.py`

Observed outcome:
1. run 1: pass
2. run 2: pass
3. run 3: pass
4. run 4: pass
5. run 5: pass

Flake result:
1. no intermittent failure observed in bounded reliability pass

## 3. Retry Boundaries

Controller runtime retry policy remains fail-closed:
1. no automatic retry for child execution failures in dispatcher
2. no retry for observability emission/canonicalization/schema failures
3. policy-disabled runs do not retry and return blocked immediately

## 4. Failure Taxonomy (Current Stable Surfaces)

Blocked-class codes:
1. `controller.envelope_invalid`
2. `controller.child_sdk_required`
3. `controller.max_depth_exceeded`
4. `controller.max_fanout_exceeded`
5. `controller.child_timeout_invalid`
6. `controller.recursion_denied`
7. `controller.cycle_denied`
8. `controller.disabled_by_policy`

Failed-class codes:
1. `controller.child_execution_failed`
2. `controller.observability_emit_failed`

## 5. Findings

1. No new reliability regression detected in targeted controller surfaces.
2. Deterministic parity and external install-path integration checks remained stable across repeated runs.

## 6. Residual Risks

1. External git-hosted repository and credentials paths are not exercised in this local reliability pass.
2. No bounded-parallel execution path exists yet; reliability findings are scoped to sequential execution only.
