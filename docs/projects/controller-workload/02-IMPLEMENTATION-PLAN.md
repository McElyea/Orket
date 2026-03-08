# Controller Workload Phase 1 Implementation Plan

Last updated: 2026-03-08
Status: Active
Owner: Orket Core
Source requirements: `docs/projects/controller-workload/01-REQUIREMENTS.md`

## 1. Objective

Implement Controller Workload Phase 1 exactly as defined in `01-REQUIREMENTS.md`, with the following non-negotiable runtime truths:

1. Child execution is sequential only.
2. Child dispatch authority is `ExtensionManager.run_workload`.
3. Supported child contract style is `sdk_v0` only.
4. Execution caps use hybrid clamp semantics (requested values clamped by runtime policy/environment caps).
5. Runtime behavior is fail-closed.
6. Error surfaces use stable error codes.
7. Provenance output and run summaries must be deterministic for equivalent inputs.

The implementation must not introduce alternate runtime paths or privileged extension execution routes.

## 2. Scope Deliverables

Phase 1 implementation must produce the following artifacts.

### 2.1 Stable Controller Specification

`docs/specs/CONTROLLER_WORKLOAD_V1.md`

This specification defines the normative controller contract used by runtime and SDK.

### 2.2 SDK Controller Primitives

`orket_extension_sdk/controller.py`

Exported through:

`orket_extension_sdk/__init__.py`

These primitives form the reusable orchestration contract for SDK workloads.

### 2.3 Runtime Dispatcher

`orket/extensions/controller_dispatcher.py`

This component performs envelope validation, cap enforcement, ancestry tracking, sequential execution, and provenance generation.

### 2.4 Bootstrap Authoring Extension

`extensions/controller_workload/`

Used for development and testing while preserving the standard extension runtime execution path.

### 2.5 Test Coverage

Tests must be labeled by verification layer:

1. contract
2. unit
3. integration

### 2.6 Deterministic Execution Evidence

Controller runs must demonstrate deterministic behavior across equivalent inputs.

## 3. Workstream Plan

### Workstream A - Spec and Authority

Tasks:

1. Author the normative controller specification:
   - `docs/specs/CONTROLLER_WORKLOAD_V1.md`
2. The specification must define:
   - envelope schema and validation rules
   - deterministic serialization requirements
   - cap clamping semantics
   - depth model
   - recursion detection behavior
   - cycle detection behavior
   - failure handling policy
   - stable error codes
   - required provenance fields
3. The spec must also define:
   - canonical serialization ordering
   - timeout normalization rules (integer seconds)
   - deterministic child execution ordering
4. Ensure the roadmap lane continues pointing to this implementation plan as the active execution authority.

Acceptance Criteria:

1. Spec includes all normative error codes defined in requirements.
2. Spec resolves all runtime-behavior ambiguities required for implementation.
3. Spec defines canonical serialization rules used for deterministic provenance.
4. Roadmap remains pointed to `02-IMPLEMENTATION-PLAN.md` for execution authority.

### Workstream B - SDK Contract Seam

Tasks:

1. Implement SDK primitives:
   - `ControllerChildCall`
   - `ControllerPolicyCaps`
   - `ControllerChildResult`
   - `ControllerRunEnvelope`
   - `ControllerRunSummary`
2. Add deterministic serialization helpers used for digest and provenance inputs.
3. Normalize timeout values to integer seconds.
4. Export controller primitives from:
   - `orket_extension_sdk/__init__.py`

Acceptance Criteria:

1. Controller primitives are importable from the SDK root.
2. Equivalent envelopes serialize to identical canonical representations.
3. Serialization helpers produce deterministic key ordering.
4. Timeout values are normalized to integer seconds.

### Workstream C - Runtime Dispatcher

Tasks:

1. Implement:
   - `orket/extensions/controller_dispatcher.py`
2. Implement the following execution pipeline.

Dispatcher Pipeline:

1. Validate `ControllerRunEnvelope`.
2. If envelope validation fails:
   - no child workloads execute
   - dispatcher returns error `controller.envelope_invalid`
   - child result list is empty
3. Validate envelope fanout does not exceed enforced cap.
4. Enforce `sdk_v0` child workload requirement.
5. Resolve runtime policy and environment caps.
6. Clamp requested caps to enforced values.
7. Initialize root depth = 0.
8. Compute child depth = parent_depth + 1.
9. Deny execution when `next_depth > max_depth`.
10. Maintain active ancestry chain.
11. Apply recursion and cycle guards.
12. Execute children sequentially in declared order.
13. Invoke child workloads using:
    - `ExtensionManager.run_workload`
14. Stop execution on the first child failure.
15. Mark remaining children as:
    - `not_attempted`
16. Record deterministic provenance entries.
17. Emit `ControllerRunSummary`.

Recursion vs Cycle Definitions:

To prevent ambiguous implementations:

Recursion Denial:

Direct or policy-prohibited re-entry of the same workload invocation.

Example:

`A -> A`

Cycle Denial:

Reappearance of a workload anywhere in the active ancestry chain.

Example:

`A -> B -> C -> A`

Both violations must fail closed using stable error codes.

Runtime Rules:

The dispatcher must guarantee:

1. no direct extension entrypoint invocation
2. no parallel execution
3. no opportunistic child reordering
4. no alternate dispatch paths

Acceptance Criteria:

1. Child execution path is exclusively:
   - `ExtensionManager.run_workload`
2. Child execution order equals envelope order.
3. Stop-on-first-failure behavior is enforced.
4. Depth violations return `controller.max_depth_exceeded`.
5. Cycle violations return `controller.cycle_denied`.
6. Legacy workloads return `controller.child_sdk_required`.

### Workstream D - Bootstrap Extension

Tasks:

1. Create bootstrap authoring extension:
   - `extensions/controller_workload/`
2. Containing:
   - `manifest.json`
   - `workload_entrypoint.py`
3. Entry point responsibilities:
   - parse workload payload
   - construct `ControllerRunEnvelope`
   - invoke controller dispatcher

Guardrail:

Bootstrap extensions must not receive privileged runtime behavior.

Controller execution must traverse the same `ExtensionManager` runtime path used by installed extensions.

Acceptance Criteria:

1. Bootstrap extension executes through the standard extension runtime path.
2. No alternate dispatch path exists.

### Workstream E - Verification and Evidence

Contract Tests:

Validate SDK primitives:

1. dataclass schema
2. envelope validation
3. deterministic serialization

Unit Tests:

Validate dispatcher mechanics:

1. cap clamp precedence
2. enforced cap values
3. depth transitions
4. max-depth denial
5. recursion denial
6. cycle denial
7. stop-on-first-failure behavior

Integration Tests:

Execute controller-child runs through `ExtensionManager`.

Required test scenarios:

1. sdk child success
2. legacy child denial
3. fanout cap denial
4. depth cap denial
5. cycle denial
6. deterministic provenance ordering

Determinism Assertion:

Equivalent controller inputs must produce identical canonical serialized `ControllerRunSummary` output, not only identical provenance ordering.

This ensures summary output is digest-stable for equivalent runs.

Evidence Generation:

Execution evidence must demonstrate:

1. deterministic ordering
2. stable error codes
3. correct cap enforcement
4. correct ancestry tracking
5. canonical summary serialization

Acceptance Criteria:

1. Tests assert error codes, not message strings.
2. Equivalent inputs produce identical canonical serialized summary output.
3. Integration tests verify authoritative runtime execution path.

## 4. Requirement Traceability Matrix

| Requirement | Implementation |
| --- | --- |
| Sequential execution | Workstream C |
| SDK child compatibility | Workstream C + integration tests |
| ExtensionManager dispatch authority | Workstream C + integration tests |
| Hybrid cap model | Workstream C + unit tests |
| Depth model enforcement | Workstream C |
| Cycle detection | Workstream C |
| Stop-on-first-failure | Workstream C |
| Stable error codes | Workstream A |
| Determinism | Workstream B + Workstream C + Workstream E |
| Bootstrap guardrail | Workstream D |

## 5. Error and Provenance Contract Lock

Stable Error Codes:

1. `controller.envelope_invalid`
2. `controller.child_sdk_required`
3. `controller.max_depth_exceeded`
4. `controller.max_fanout_exceeded`
5. `controller.child_timeout_invalid`
6. `controller.recursion_denied`
7. `controller.cycle_denied`
8. `controller.child_execution_failed`

Per-Child Provenance Fields:

Each child result must record:

1. `target_workload`
2. `status`
3. `requested_timeout`
4. `enforced_timeout`
5. `requested_caps`
6. `enforced_caps`
7. `artifact_refs`
8. `normalized_error`

Provenance entries must appear in execution order.

## 6. Completion Gate

Phase 1 is complete when:

1. SDK primitives exist and are publicly exported.
2. Dispatcher enforces caps, depth, recursion/cycle, and stop-on-first-failure.
3. Child execution is strictly sequential and deterministic.
4. Non-SDK workloads are denied with stable error codes.
5. Provenance output includes all required fields in deterministic order.
6. Contract, unit, and integration tests pass for the authoritative runtime path.
