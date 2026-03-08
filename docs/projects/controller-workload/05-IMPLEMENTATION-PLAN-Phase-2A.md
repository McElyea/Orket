# Controller Workload Phase 2A Implementation Plan

Last updated: 2026-03-08
Status: Active
Owner: Orket Core
Source requirements: `docs/projects/controller-workload/04-REQUIREMENTS-Phase-2A.md`
Runtime contract authority: `docs/specs/CONTROLLER_WORKLOAD_V1.md`
Observability contract authority: `docs/specs/CONTROLLER_OBSERVABILITY_V1.md`
Schema authority: `schemas/controller_observability_v1.json`

## 1. Objective

Implement Phase 2A exactly as defined in `04-REQUIREMENTS-Phase-2A.md` for initiative steps 11-13:
1. operator runbook and authoring guidance
2. recursion/cycle/error hardening
3. deterministic controller observability contract implementation

This slice is bounded to operational clarity and runtime hardening. Externalization, rollout controls, replay/parity expansion, and CI conformance gate work are intentionally out of scope.

Phase 2A normative run-result invariants:
1. `result = success` requires `error_code = null`.
2. `result in {failed, blocked}` requires `error_code != null`.
3. If any child execution result is `success`, controller run result must not be `blocked`.

Terminology lock:
1. `failed` is the authoritative runtime/observability result term.
2. Human-facing `failure` wording is descriptive only and must not alter contract vocabularies.

## 2. Scope Deliverables

### 2.1 Operational Documentation

1. `docs/runbooks/controller-workload-operator.md`
2. `docs/guides/controller-workload-authoring.md`

### 2.2 Runtime Hardening

1. recursion/cycle/error normalization hardening in controller runtime paths
2. no alternate dispatch paths or direct child entrypoint invocation

### 2.3 Observability Contract Implementation

1. observability helper module at `orket/extensions/controller_observability.py`
2. deterministic event construction and canonicalization aligned to `CONTROLLER_OBSERVABILITY_V1.md`
3. schema-backed payload validation against `schemas/controller_observability_v1.json`

### 2.4 Verification Artifacts

1. contract tests for schema and event contract behavior
2. unit tests for hardening logic and normalization rules
3. integration tests through `ExtensionManager.run_workload`
4. phase evidence report with path/result classification

Evidence classification scope:
1. classification is recorded per executed test/integration case and, where applicable, per end-to-end controller run artifact.
2. evidence labels are reporting-only and non-normative.
3. runtime and observability result vocabularies remain contract-authoritative from `CONTROLLER_WORKLOAD_V1.md` and `CONTROLLER_OBSERVABILITY_V1.md`.

## 3. Workstream Plan

### Workstream A - Operator Documentation

Tasks:
1. Author operator runbook with `primary`, `fallback`, `degraded`, `blocked` path classification.
2. Document failure triage for envelope invalid, sdk child denial, depth/fanout denial, recursion/cycle denial, and child execution failure.
3. Document expected provenance and observability outputs per path class.
4. Include a compact operator decision table mapping path classification to first triage action.

Acceptance:
1. Runbook enables diagnosis without implementation-level source inspection.
2. Terminology matches stable controller error code surfaces.
3. Runbook distinguishes stable operator-facing contract fields from implementation-detail diagnostics.

### Workstream B - Authoring Guidance

Tasks:
1. Author controller workload authoring guide for cap requests, child order guarantees, and denial semantics.
2. Document that child order guarantees apply to accepted envelope child order only, not declared-but-rejected children.
3. Document accepted envelope assumptions and fanout semantics.
4. Document not-attempted behavior after first failure for later siblings in the same accepted envelope only (no implication for retries or independent runs).

Acceptance:
1. Authoring guidance is contract-aligned with workload and observability specs.
2. Guidance does not describe unsupported child contract styles or alternate runtime paths.

### Workstream C - Runtime Hardening

Tasks:
1. Harden recursion/cycle rule handling where ambiguity remains.
2. Harden normalized child failure error envelope behavior for structured denials, raised exceptions, malformed child outputs, and unexpected non-structured error values.
3. Normalize malformed and non-structured child error shapes to stable controller error surfaces rather than propagating raw provider/runtime payloads.
4. Preserve stable controller error-code identities and fail-closed behavior for controller runtime and observability-emission paths touched by this slice.
5. Ensure normalization does not invent semantic child states beyond contract-authorized statuses.
6. Preserve sequential execution and stop-on-first-failure behavior.

Acceptance:
1. No new controller error codes are introduced beyond stable codes already authorized by `CONTROLLER_WORKLOAD_V1.md`, including `controller.observability_emit_failed` where defined by contract.
2. Existing stable codes remain behaviorally consistent.
3. Regression tests show no determinism/order drift.
4. If any child execution result is `success`, run result is never `blocked`.

### Workstream D - Observability Runtime Implementation

Tasks:
1. Implement `orket/extensions/controller_observability.py` with:
   - `emit_controller_run(...)`
   - `emit_controller_child(...)`
   - `validate_observability_schema(...)`
   - `canonicalize_event(...)`
2. Enforce `post_execution_batch_emit` behavior and run-level atomic batch semantics.
3. Enforce atomic emission boundary: events must be fully constructed, canonicalized, and schema-validated in-memory as one complete batch before any sink write; if any event fails canonicalization, validation, or sink preparation, zero events are emitted.
4. Treat sink preparation as including serialization readiness, sink initialization/readiness, and durable-write readiness checks when applicable.
5. Enforce canonical field ordering and deterministic canonicalization for semantically identical inputs across repeated runs of the same code version.
6. Enforce canonicalization-before-schema-validation ordering, and require both to succeed before emission.
7. Projection for deterministic comparison is test/evidence-only unless explicitly authorized by the observability contract; projection is limited to contract-authorized non-semantic identifiers (for example `run_id`) and must not omit, rewrite, or normalize semantic result/error/order fields.
8. Ensure `controller.observability_emit_failed` fail-closed behavior when canonicalization/validation/emission fails.

Acceptance:
1. No partial event streams are emitted.
2. `controller_run` is the first emitted event in every non-empty batch and emits before all child events.
3. Emitted batches never contain child events without exactly one preceding `controller_run` event in that same batch.
4. Accepted-envelope child event count equals `accepted_fanout`.
5. Envelope invalid and fanout exceeded emit zero child events.
6. Result/error invariants are enforced (`success -> null error_code`; `{failed, blocked} -> non-null error_code`).

### Workstream E - Test and Evidence

Contract tests:
1. validate event schema, required fields, enum constraints, and type constraints
2. validate declared/accepted fanout schema semantics
3. validate result/error invariants
4. validate envelope-invalid zero-child-event behavior
5. validate max-fanout-exceeded zero-child-event behavior

Unit tests:
1. validate blocked vs failed mapping behavior
2. validate child failure error-code assignment
3. validate not-attempted timeout and error semantics
4. validate atomic emission failure behavior

Integration tests:
1. execute through `ExtensionManager.run_workload`
2. verify observability ordering matches provenance ordering
3. verify run result is not blocked when any child succeeds
4. verify equivalence of canonical event streams after run_id projection
5. verify no alternate dispatch path is reachable for child execution through `ExtensionManager.run_workload`

Evidence output:
1. classify path as `primary`, `fallback`, `degraded`, or `blocked`
2. record contract-authoritative runtime result as `success`, `failed`, or `blocked`
3. optional non-authoritative reporting note may classify scenario narrative as `partial_success` or `environment_blocker` for human review only
4. capture exact failing step and exact error for blocked/failed runs
5. exact failing step must reference a concrete runtime phase or function/stage label so evidence remains comparable across runs

## 4. Implementation Order

1. documentation foundations (Workstream A and B)
2. runtime hardening seams (Workstream C)
3. observability helper and schema enforcement (Workstream D)
4. test completion and evidence capture (Workstream E)

## 5. Completion Gate

Phase 2A implementation is complete when:
1. runbook and authoring docs are published and contract-aligned
2. runtime hardening changes preserve all Phase 1 invariants
3. observability helper exists and is schema-backed
4. contract/unit/integration tests pass for the changed paths
5. evidence report is recorded with required path/result/error detail

## 6. Out-of-Scope Guardrail

This plan must not include:
1. replay/parity expansion
2. CI conformance gate implementation
3. externalized extension template/migration execution
4. rollout controls or feature flags
5. live external install-path verification

Those remain in later initiative slices after Phase 2A closeout.
