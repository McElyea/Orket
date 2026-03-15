# Orket Truthful Runtime Hardening Phase A Implementation Plan

Last updated: 2026-03-09
Status: Completed (archived closeout)
Owner: Orket Core
Canonical lane plan: `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`

## Closeout Verification (2026-03-10)

1. Contract tests (layer: contract):  
   `python -m pytest tests/runtime/test_provider_truth_table.py tests/runtime/test_run_phase_contract.py tests/runtime/test_timeout_streaming_contracts.py tests/runtime/test_state_transition_registry.py tests/runtime/test_runtime_truth_contracts.py tests/runtime/test_protocol_error_codes.py tests/runtime/test_protocol_error_code_adoption.py`
2. Live acceptance gate (layer: integration/live-truth governance):  
   `python scripts/governance/run_runtime_truth_acceptance_gate.py --workspace .`
3. Observed path: primary
4. Observed result: success (`ok=true`, `failures=[]`)

## 1. Objective

Freeze canonical runtime vocabulary and contract surfaces so behavior is explicit, testable, and shared across docs, schemas, tests, and runtime code.

## 2. Scope Deliverables

1. Capability registry contract for tools/providers/models.
2. Provider truth table contract for support surfaces (`streaming`, JSON mode, tools, image input, seed control, context length, repair tolerance).
3. Canonical run phase contract.
4. Fail-open vs fail-closed registry by subsystem.
5. Degradation taxonomy and runtime vocabulary freeze.
6. Timeout semantics contract and streaming semantics contract.
7. State transition registry baseline for session/run/tool/voice/UI.
8. Event ordering rules and atomic finalize contract.
9. Error-code discipline alignment for user-visible failures.

## 3. Detailed Workstreams

### Workstream A1 - Contract Draft and Freeze
Tasks:
1. Draft/update specs for capability registry, provider truth table, run phases, degradation taxonomy, and timeout semantics.
2. Define canonical vocabulary set and status/error taxonomy.
3. Align error-code naming with stable machine-readable codes.

Acceptance:
1. vocabulary is compact and canonical.
2. each defined runtime phase and degraded state has one authoritative definition.

### Workstream A2 - State and Ordering Semantics
Tasks:
1. Define allowed transitions for session/run/tool/voice/UI states.
2. Define ordering semantics for persistence, observability, and user-visible emission.
3. Define atomic finalize semantics and partial-success handling.

Acceptance:
1. illegal transitions are clearly forbidden.
2. finalize and ordering semantics are implementation-testable.

### Workstream A3 - Schema and Consistency Baseline
Tasks:
1. Establish schema authority map for each artifact class.
2. Specify ownership boundaries for schema changes.
3. Define initial consistency-check targets across docs/schemas/tests/runtime vocabulary.

Acceptance:
1. schema ownership and authority is explicit.
2. phase artifacts support later cross-spec drift automation.

## 4. Verification Plan

1. Contract tests for run phases, state transition registry, and vocabulary enums.
2. Validation tests for timeout/streaming semantics normalization.
3. Consistency checks ensuring runtime vocabulary maps to docs/spec definitions.

## 5. Completion Gate

Phase A is complete when:
1. all listed contract deliverables exist and are authoritative,
2. runtime vocabulary/degradation/error semantics are frozen for this lane version,
3. ordering/finalize semantics are explicitly testable.
