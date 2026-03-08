# Controller Workload Phase 1 Bootstrap (SDK-First)

Last updated: 2026-03-08
Status: Proposed
Owner: Orket Core

## 1. Summary

Launch a new active development lane `controller-workload` under Priority Now.

The controller workload introduces deterministic orchestration of SDK child workloads while preserving the existing Orket extension runtime model.

Phase 1 establishes the contract seam in the SDK, implements a runtime dispatcher enforcing policy and determinism, and provides a bootstrap controller extension for development.

This phase intentionally prioritizes:
1. deterministic execution
2. runtime truth
3. ExtensionManager authority
4. fail-closed behavior
5. spec-first development

## 2. Current Extension Runtime Layout (Confirmed)

Installed runtime copies:
1. `.orket/durable/extensions/<extension>-<hash>`

Managed via:
1. `orket/extensions/manager.py`

Extension catalog:
1. `.orket/durable/config/extensions_catalog.json`

Workload run artifacts:
1. `workspace/extensions/<extension_id>/...`

Phase-1 bootstrap authoring path:
1. `extensions/controller_workload/`

Important:
1. The bootstrap path is authoring only.
2. All execution must still route through the standard extension runtime path.

## 3. Key Implementation Changes

### 3.1 Project Bootstrap and Authority Wiring

Add the controller workload project package.

New files:
1. `docs/projects/controller-workload/01-REQUIREMENTS.md`
2. `docs/projects/controller-workload/02-IMPLEMENTATION-PLAN.md`
3. `docs/specs/CONTROLLER_WORKLOAD_V1.md`

Update:
1. `docs/ROADMAP.md`

Add:
1. Priority Now lane entry
2. Project Index row for `controller-workload`

Do not modify:
1. `CURRENT_AUTHORITY.md`

Unless this phase changes canonical runtime, install, or test commands.

### 3.2 SDK-Owned Controller Contract

Add reusable controller primitives to the SDK:
1. `orket_extension_sdk/controller.py`

Public types:
1. `ControllerChildCall`
2. `ControllerPolicyCaps`
3. `ControllerChildResult`
4. `ControllerRunEnvelope`
5. `ControllerRunSummary`

Export them via:
1. `orket_extension_sdk/__init__.py`

These primitives must remain generic orchestration constructs so future workloads can reuse them.

Examples of future reuse:
1. pipeline workloads
2. retry orchestrators
3. DAG executors
4. distributed fanout
5. routing workloads

Controller semantics must not be hard-coded to the `controller_workload` extension.

### 3.3 Runtime Dispatcher

Add a controller dispatcher under:
1. `orket/extensions/`

Example location:
1. `orket/extensions/controller_dispatcher.py`

Dispatcher responsibilities:
1. validate `ControllerRunEnvelope`
2. enforce SDK child restriction
3. resolve policy caps
4. apply runtime clamping
5. track execution depth
6. detect recursion/cycles
7. execute children sequentially
8. collect deterministic provenance
9. produce `ControllerRunSummary`

Child invocation must always use:
1. `ExtensionManager.run_workload`

Direct invocation of child extension entrypoints is forbidden.

### 3.4 Runtime Policy and Cap Controls

Controller execution uses a hybrid cap model.

Payloads may request execution limits, but runtime policy enforces hard caps.

Default caps:
1. `max_depth = 1`
2. `max_fanout = 5`
3. `child_timeout_seconds = 900`

Payload values are clamped against runtime policy.

Runtime must record:
1. requested values
2. policy caps
3. enforced values

In provenance.

### 3.5 Hybrid Extension Source Layout

Bootstrap extension location:
1. `extensions/controller_workload/`

Structure:

```text
extensions/controller_workload/
    manifest.json
    workload_entrypoint.py
```

The bootstrap extension:
1. exists for development convenience
2. must not receive special runtime privileges
3. must still dispatch through ExtensionManager

Production installation continues to use:
1. `orket extensions install <repo-or-path>`

With catalog records.

### 3.6 Spec Extraction Requirement

Before runtime logic expands, extract the controller contract to:
1. `docs/specs/CONTROLLER_WORKLOAD_V1.md`

Implementation plans must reference the spec instead of embedding behavioral assumptions.

## 4. Locked Behavioral Decisions

The following decisions are normative.

### 4.1 Execution Model

Controller execution is:
1. sequential only

Child order:
1. exactly equals envelope order

Runtime must not:
1. parallelize
2. reorder
3. batch
4. speculatively execute

### 4.2 SDK Compatibility

Controller v0 supports only:
1. `sdk_v0` workloads

Legacy workloads must be denied with a stable error code.

### 4.3 Runtime Dispatch Authority

Child workloads must be invoked through:
1. `ExtensionManager.run_workload`

Direct entrypoint invocation is forbidden.

### 4.4 Hybrid Cap Model

Execution caps follow this rule:
1. `enforced_value = clamp(requested_value, policy_cap)`

Both requested and enforced values must be recorded.

### 4.5 Depth Model

Depth begins at:
1. root controller depth = 0

Child depth:
1. `child_depth = parent_depth + 1`

Execution is denied when:
1. `next_depth > max_depth`

### 4.6 Cycle Detection

Active ancestry must be tracked.

Example denial:
1. `A -> B -> C -> A`

Cycle detection triggers:
1. `controller.cycle_denied`

Execution fails closed.

### 4.7 Child Failure Policy

Controller v0 uses:
1. stop-on-first-failure

Behavior:
1. completed children recorded
2. failed child recorded
3. remaining children marked `not_attempted`

Controller summary state:
1. `failed`

## 5. Stable Error Codes

The following error codes are normative:
1. `controller.envelope_invalid`
2. `controller.child_sdk_required`
3. `controller.max_depth_exceeded`
4. `controller.max_fanout_exceeded`
5. `controller.child_timeout_invalid`
6. `controller.recursion_denied`
7. `controller.cycle_denied`
8. `controller.child_execution_failed`

Tests must assert error codes, not error messages.

## 6. Determinism Requirements

To ensure stable provenance and reproducibility:
1. child execution order equals input order
2. canonical serialization must be used for digest inputs
3. object keys must serialize in deterministic order
4. timeout units must normalize to integer seconds
5. equivalent inputs must produce identical provenance ordering

## 7. Provenance Requirements

Each child result must record:
1. `target_workload`
2. `status`
3. `requested_timeout`
4. `enforced_timeout`
5. `requested_caps`
6. `enforced_caps`
7. `artifact_refs`
8. `normalized_error`

Child results must appear in execution order.

## 8. Test Plan

Testing must cover the following areas.

Contract tests:
1. SDK dataclasses:
   - `ControllerChildCall`
   - `ControllerPolicyCaps`
   - `ControllerRunEnvelope`
   - `ControllerRunSummary`
2. Validate:
   - structure
   - serialization
   - determinism

Integration tests:
1. controller execution through ExtensionManager
2. test cases:
   - SDK child invocation success
   - legacy child denial
   - fanout cap enforcement
   - depth cap enforcement
   - cycle detection
   - stop-on-first-failure behavior
   - deterministic provenance ordering

Unit tests:
1. policy resolver:
   - payload request
   - environment caps
   - runtime policy caps
2. ensure correct clamp precedence

## 9. Implementation Order

Slice 1 - Documentation:
1. add:
   - `docs/projects/controller-workload/01-REQUIREMENTS.md`
   - `docs/projects/controller-workload/02-IMPLEMENTATION-PLAN.md`
   - `docs/specs/CONTROLLER_WORKLOAD_V1.md`
2. update:
   - `docs/ROADMAP.md`

Slice 2 - SDK Contract:
1. add:
   - `orket_extension_sdk/controller.py`
2. export types via SDK
3. add contract tests

Slice 3 - Runtime Dispatcher:
1. add:
   - `orket/extensions/controller_dispatcher.py`
2. implement:
   - envelope validation
   - cap resolution
   - depth tracking
   - cycle detection
   - sequential execution
   - provenance collection

Slice 4 - Bootstrap Extension:
1. add:
   - `extensions/controller_workload/`
2. entrypoint constructs envelope and calls dispatcher

Slice 5 - Integration Proof:
1. add fixture extensions for testing
2. validate:
   - SDK child execution
   - legacy denial
   - cap enforcement
   - cycle detection
   - deterministic provenance

## 10. Roadmap Entry

Priority Now:
1. Controller Workload - introduce SDK controller primitives enabling deterministic sequential orchestration of SDK child workloads through ExtensionManager with runtime-enforced depth, fanout, and timeout caps and stable provenance recording.

Project Index:
1. `controller-workload` - controller orchestration bootstrap, SDK contract seam, runtime dispatcher, and sequential execution policy.

## 11. Bootstrap Guardrail

The in-repo bootstrap extension must not receive privileged runtime behavior relative to installed extensions.

All controller child execution must traverse the same ExtensionManager runtime path used by installed and cataloged extensions.

## 12. Phase Success Criteria

Phase 1 is complete when:
1. controller SDK primitives exist
2. controller dispatcher enforces runtime caps
3. child execution is deterministic and sequential
4. recursion/cycle protection works
5. provenance recording is stable
6. legacy workloads are denied
7. integration tests validate runtime truth

## Result

This phase introduces orchestration capability to Orket while maintaining:
1. deterministic runtime behavior
2. single runtime authority
3. spec-driven implementation
4. verifiable provenance
5. fail-closed safety

Controller workloads become a foundational orchestration primitive that future workloads can reuse without introducing architectural drift.
