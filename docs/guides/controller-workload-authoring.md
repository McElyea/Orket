# Controller Workload Authoring Guide

Last updated: 2026-03-08
Status: Active
Owner: Orket Core

Contract authority:
`docs/specs/CONTROLLER_WORKLOAD_V1.md`

Related operator runbook:
`docs/runbooks/controller-workload-operator.md`

## 1. Purpose

Define how to author controller workload payloads that are accepted deterministically by the current runtime.

This guide is authoritative for:
1. cap-request semantics
2. child ordering guarantees
3. denial behavior and failure boundaries

## 2. Required Envelope Fields

Provide these fields for each controller run input:
1. `controller_workload_id`
2. `parent_depth` (integer `>= 0`)
3. `ancestry` (list of workload ids in active chain)
4. `children` (non-empty list)

The runtime layer supplies `controller_contract_version = "controller.workload.v1"` automatically in the in-repo controller workload entrypoint, but explicitly setting it is allowed when calling dispatcher-level paths.

## 3. Child Declaration Rules

Each child entry must include:
1. `target_workload`
2. `contract_style = "sdk_v0"`

Optional child fields:
1. `payload`
2. `timeout_seconds`
3. `metadata`

Authoring constraints:
1. only SDK v0 child workloads are supported
2. direct self-target (`target_workload == controller_workload_id`) is denied
3. workload ids already present in ancestry are denied as cycles

## 4. Cap Request Semantics

Controller caps use hybrid clamp semantics:
1. author declares `requested_caps`
2. runtime enforces policy caps
3. final enforced value is `min(requested_or_default, runtime_policy_cap)`

Cap fields:
1. `max_depth`
2. `max_fanout`
3. `child_timeout_seconds`

Timeout normalization:
1. timeout values are normalized to integer seconds
2. non-finite or `<= 0` values fail closed with `controller.child_timeout_invalid`

## 5. Child Order Guarantee

Deterministic order guarantee applies to accepted envelope children only:
1. runtime executes children strictly in declared order
2. runtime does not reorder accepted children
3. if envelope is rejected before acceptance (for example `controller.envelope_invalid` or `controller.max_fanout_exceeded`), no child order guarantee applies because no children are accepted

## 6. Stop-on-First-Failure Boundary

Within a single accepted envelope run:
1. execution stops at the first child failure/denial
2. later siblings in that same accepted envelope are marked `not_attempted`

Non-implications:
1. this does not define retry policy
2. this does not define behavior for independent future runs
3. this does not imply cross-run carryover of `not_attempted`

## 7. Stable Denial and Failure Codes

Current stable controller error surfaces:
1. `controller.envelope_invalid`
2. `controller.child_timeout_invalid`
3. `controller.max_fanout_exceeded`
4. `controller.max_depth_exceeded`
5. `controller.recursion_denied`
6. `controller.cycle_denied`
7. `controller.child_sdk_required`
8. `controller.child_execution_failed`
9. `controller.disabled_by_policy`

Use stable codes for assertions and diagnostics; do not key automation logic on free-form error text.

## 8. Authoring Template (Minimal)

```json
{
  "controller_workload_id": "controller_workload_v1",
  "parent_depth": 0,
  "ancestry": [],
  "requested_caps": {
    "max_depth": 2,
    "max_fanout": 5,
    "child_timeout_seconds": 300
  },
  "children": [
    {
      "target_workload": "sdk_child_a_v1",
      "contract_style": "sdk_v0",
      "payload": {
        "token": "a"
      }
    },
    {
      "target_workload": "sdk_child_b_v1",
      "contract_style": "sdk_v0",
      "payload": {
        "token": "b"
      }
    }
  ]
}
```

## 9. Author Checklist

1. Keep child list intentional and ordered.
2. Request caps explicitly when behavior depends on clamp outcomes.
3. Avoid recursive or cyclic target graphs.
4. Use SDK v0 child workloads only.
5. Validate timeouts and fanout before submission.
6. Verify outputs from `controller_summary` and child artifact refs for deterministic debugging.
