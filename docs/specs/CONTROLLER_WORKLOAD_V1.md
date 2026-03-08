# Controller Workload Contract v1

Last updated: 2026-03-08
Status: Active
Owner: Orket Core

## Contract ID
1. `controller.workload.v1`

## Purpose
1. Define the normative controller-workload runtime contract shared by SDK and runtime dispatcher.
2. Lock deterministic behavior for child orchestration and provenance output.

## Runtime Truths (Normative)
1. Child execution is sequential only.
2. Child dispatch authority is `ExtensionManager.run_workload`.
3. Supported child contract style is `sdk_v0` only.
4. Cap enforcement uses hybrid clamp semantics.
5. Runtime behavior is fail-closed.
6. Error surfaces use stable error codes.
7. Equivalent inputs must produce identical canonical summary serialization.

## Envelope Contract

Required top-level fields:
1. `controller_contract_version` with exact value `controller.workload.v1`
2. `controller_workload_id`
3. `parent_depth`
4. `ancestry`
5. `children`

Optional fields:
1. `requested_caps`
2. `metadata`

Child call required fields:
1. `target_workload`
2. `contract_style` (exact value `sdk_v0`)

Child call optional fields:
1. `payload`
2. `timeout_seconds`
3. `metadata`

Validation rules:
1. `parent_depth` is an integer `>= 0`.
2. `children` preserves author-declared order and is not reordered by runtime.
3. `timeout_seconds` normalizes to integer seconds.
4. Invalid timeout input fails with `controller.child_timeout_invalid`.

## Cap and Clamp Semantics

Default runtime caps:
1. `max_depth = 1`
2. `max_fanout = 5`
3. `child_timeout_seconds = 900`

Hybrid clamp rule:
1. `enforced_value = min(requested_value_or_default, policy_cap)`

Runtime must record:
1. requested caps
2. policy caps
3. enforced caps

## Depth, Recursion, and Cycle Semantics
1. Root depth starts at `0`.
2. Child depth is `parent_depth + 1`.
3. Execution denies when `next_depth > max_depth` with `controller.max_depth_exceeded`.
4. Recursion denial applies to prohibited re-entry patterns, including direct re-entry (`A -> A`), and returns `controller.recursion_denied`.
5. Cycle denial applies when a workload reappears anywhere in the active ancestry chain (`A -> B -> C -> A`) and returns `controller.cycle_denied`.
6. Violations fail closed with no alternate execution path.

## Dispatch and Failure Policy
1. Runtime executes children strictly in envelope order.
2. Runtime must invoke children through `ExtensionManager.run_workload`.
3. Direct entrypoint invocation is forbidden.
4. Execution stops on first child failure.
5. Remaining children are marked `not_attempted`.
6. Summary status is `failed` when any child fails or a contract guard fails.

## Run Result Vocabulary (Observability Alignment)
Run-level result vocabulary for observability surfaces is:
1. `success`
2. `failed`
3. `blocked`

Normative alignment rules:
1. `success` means controller execution completed with no child failure and no contract denial.
2. `failed` means execution began but did not complete successfully, or a runtime-adjacent authoritative contract failed.
3. `blocked` means execution terminated without any child workload successfully completing.
4. If any child status is `success`, run result must not be `blocked`.

## Stable Error Codes
1. `controller.envelope_invalid`
2. `controller.child_sdk_required`
3. `controller.max_depth_exceeded`
4. `controller.max_fanout_exceeded`
5. `controller.child_timeout_invalid`
6. `controller.recursion_denied`
7. `controller.cycle_denied`
8. `controller.child_execution_failed`
9. `controller.observability_emit_failed`

## Provenance Contract

Each child result must include:
1. `target_workload`
2. `status`
3. `requested_timeout`
4. `enforced_timeout`
5. `requested_caps`
6. `enforced_caps`
7. `artifact_refs`
8. `normalized_error`

Provenance ordering rule:
1. Child provenance appears in execution order and must not be post-sorted.

## Deterministic Serialization Contract
1. Canonical serialization uses JSON with sorted object keys and compact separators `(",", ":")`.
2. List ordering is preserved as provided by execution order.
3. Timeout values are normalized to integer seconds before canonical serialization.
4. Equivalent inputs must yield byte-identical canonical serialized `ControllerRunSummary` payloads.
5. Error assertions must use stable error codes, not free-form message text.
