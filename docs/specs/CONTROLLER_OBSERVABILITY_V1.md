# CONTROLLER_OBSERVABILITY_V1

Last updated: 2026-03-08
Status: Active
Owner: Orket Core

Runtime contract authority:
`docs/specs/CONTROLLER_WORKLOAD_V1.md`

Phase authority:
`docs/projects/archive/controller-workload/CW03082026-Phase2D/04-REQUIREMENTS-Phase-2D.md`

Machine-readable schema:
`schemas/controller_observability_v1.json`

## 1. Purpose

Define the deterministic observability contract for controller workload execution.

This specification defines:
1. controller-run observability events
2. child-execution observability events
3. deterministic event ordering
4. canonical event field definitions
5. correlation guarantees with provenance records

Observability events provide operational telemetry only.

The authoritative execution record remains the provenance artifacts defined in `CONTROLLER_WORKLOAD_V1.md`.

## 2. Observability Model

Controller telemetry consists of two event types:

| Event Type | Description |
|---|---|
| `controller_run` | controller workload execution summary |
| `controller_child` | individual child workload execution result |

Observability V1 uses a `post_execution_batch_emit` model.

All observability events for a controller run are emitted only after the controller run state is finalized.

Events are then emitted synchronously as a deterministic batch in canonical order:
1. `controller_run`
2. `controller_child` events in `child_index` order

`controller_run` is a deterministic run-summary observability event.

## 3. Deterministic Ordering Rules

The observability layer must guarantee:
1. The `controller_run` event is emitted before any `controller_child` event.
2. `controller_child` events are emitted in `child_index` order.
3. Event ordering must not depend on asynchronous logging transport, batching, or delivery timing.
4. Equivalent controller inputs must produce identical ordered event streams after canonical comparison projection.

This preserves deterministic behavior across:

```text
runtime execution
        ↓
provenance ordering
        ↓
observability ordering
```

## 4. Run Finalization Lifecycle

Controller run finalization occurs in the following sequence:
1. compute execution outcome
2. build and validate canonical observability batch
3. determine final run result and `error_code` (including `controller.observability_emit_failed` override if needed)
4. emit the full observability batch atomically
5. persist final provenance summary

Failure rule:
1. If observability batch construction, validation, or atomic emission fails:
   - no observability events are emitted
   - final `result = "failed"`
   - final `error_code = "controller.observability_emit_failed"`

This lifecycle is normative.

Provenance is written only after the final result is known, eliminating run-summary mutation risk.

### 4.1 Atomic Emission Implementation Contract

`No partial event streams` is a required runtime property.

Implementations must guarantee atomic run-level emission using a mechanism that validates and materializes the complete canonical batch before any externally visible event is published.

Acceptable implementation shapes include:
1. local validated batch write followed by single publish step
2. transactional append of the full event batch
3. equivalent all-or-nothing mechanism with identical observable behavior

Implementations must not emit individual events opportunistically before full batch validation succeeds.

## 5. Controller Run Event

Event name:
`controller_run`

Required fields:

| Field | Description |
|---|---|
| `event` | fixed event name `controller_run` |
| `run_id` | unique controller run identifier |
| `controller_workload` | controller workload identifier |
| `execution_depth` | runtime execution depth |
| `declared_fanout` | raw envelope child count, or `null` when unparseable |
| `accepted_fanout` | accepted child count after envelope validation |
| `requested_caps` | caps requested by payload |
| `enforced_caps` | caps enforced by runtime |
| `result` | controller run result |
| `error_code` | stable controller error code or `null` |

### 5.1 run_id Requirements

`run_id` must be identical across:
1. runtime execution state
2. provenance artifacts
3. observability events

for the same controller run.

`run_id` is a correlation identifier and is excluded from deterministic event-stream equality comparisons.

### 5.2 Allowed Result Values

Allowed result values are:
1. `success`
2. `failed`
3. `blocked`

No additional result values are permitted in V1.

### 5.3 Result and Error Invariants

The following invariants are normative:
1. `result = "success"` requires `error_code = null`
2. `result = "failed"` requires `error_code != null`
3. `result = "blocked"` requires `error_code != null`

### 5.4 Stable Error Code Mapping

| Stable Code | Run Result | Child Status Behavior |
|---|---|---|
| `controller.envelope_invalid` | `blocked` | no child events |
| `controller.child_sdk_required` | `blocked` | failing child = `failure`; later children = `not_attempted` |
| `controller.max_depth_exceeded` | `blocked` | failing child = `failure`; later children = `not_attempted` |
| `controller.max_fanout_exceeded` | `blocked` | no child events |
| `controller.child_timeout_invalid` | `blocked` | failing child = `failure`; later children = `not_attempted` |
| `controller.recursion_denied` | `blocked` | failing child = `failure`; later children = `not_attempted` |
| `controller.cycle_denied` | `blocked` | failing child = `failure`; later children = `not_attempted` |
| `controller.disabled_by_policy` | `blocked` | no child events |
| `controller.child_execution_failed` | `failed` | failing child = `failure`; later children = `not_attempted` |
| `controller.observability_emit_failed` | `failed` | child statuses unchanged if already computed; no partial event stream may be emitted |

Normative rule:
1. `blocked` indicates execution terminated without any child workload successfully completing.
2. `failed` indicates execution began but did not complete successfully, or a required runtime-adjacent contract failed.

### 5.5 Blocked Run Definition

A run is `blocked` when execution terminates without any child workload successfully completing.

A blocked run may still contain a `controller_child` event with `status = "failure"` at the first denied child index, followed by `not_attempted` events for later children.

The following are per-child validation checks and are not strictly envelope-level checks:
1. `controller.child_sdk_required`
2. `controller.recursion_denied`
3. `controller.cycle_denied`
4. `controller.child_timeout_invalid`

### 5.6 Blocked Run Invariant

If any `controller_child` event has `status = "success"`, the `controller_run` result must not be `blocked`.

### 5.7 Fanout Semantics

Accepted envelope:
1. `declared_fanout = accepted_fanout = number of declared children`

Rejected envelope:
1. `declared_fanout = raw envelope child count if parseable`
2. `declared_fanout = null` if child collection is missing or unparseable
3. `accepted_fanout = 0`

Cardinality rule:
1. `controller_child` event count must equal `accepted_fanout`

### 5.8 Canonical Field Order for controller_run

`controller_run` payload fields must serialize in exactly this order:
1. `event`
2. `run_id`
3. `controller_workload`
4. `execution_depth`
5. `declared_fanout`
6. `accepted_fanout`
7. `requested_caps`
8. `enforced_caps`
9. `result`
10. `error_code`

Nested objects such as `requested_caps` and `enforced_caps` must use the canonical key order defined in `CONTROLLER_WORKLOAD_V1.md`.

### 5.9 Example

```json
{
  "event": "controller_run",
  "run_id": "run_42",
  "controller_workload": "controller_workload",
  "execution_depth": 0,
  "declared_fanout": 5,
  "accepted_fanout": 5,
  "requested_caps": {
    "max_depth": 2,
    "max_fanout": 5
  },
  "enforced_caps": {
    "max_depth": 1,
    "max_fanout": 5
  },
  "result": "failed",
  "error_code": "controller.child_execution_failed"
}
```

## 6. Controller Child Event

Event name:
`controller_child`

Required fields:

| Field | Description |
|---|---|
| `event` | fixed event name `controller_child` |
| `run_id` | controller run identifier |
| `child_index` | deterministic child execution index |
| `execution_order` | identical to `child_index` |
| `child_workload` | child workload identifier |
| `status` | child execution result |
| `requested_timeout` | timeout requested for child |
| `enforced_timeout` | timeout enforced by runtime or `null` |
| `error_code` | normalized error code if failure, else `null` |

### 6.1 execution_order Semantics

`execution_order == child_index`

Both values reflect deterministic runtime execution order.

### 6.2 Allowed Status Values

Allowed status values are:
1. `success`
2. `failure`
3. `not_attempted`

No additional status values are permitted in V1.

### 6.3 Event Emission Rule

A `controller_child` event must be emitted for every declared child workload in an accepted envelope, including children whose status is `not_attempted`.

This ensures that child event count equals `accepted_fanout`.

### 6.4 Child Error Code Rules

For `controller_child` events:
1. `status = success` => `error_code = null`
2. `status = not_attempted` => `error_code = null`
3. `status = failure` => `error_code` must equal the stable controller code that caused the failure at that child index

Examples of valid failure `error_code` values:
1. `controller.child_sdk_required`
2. `controller.recursion_denied`
3. `controller.cycle_denied`
4. `controller.child_timeout_invalid`
5. `controller.child_execution_failed`

Later children with `status = not_attempted` must always have `error_code = null`.

### 6.5 not_attempted Semantics

For `controller_child` events with `status = "not_attempted"`:
1. `requested_timeout = declared/requested value if present, otherwise null`
2. `enforced_timeout = null`
3. `error_code = null`

Reason: the child was declared but never executed.

### 6.6 Early-Denial Cardinality Rule

If `controller.envelope_invalid` occurs:
1. the envelope is rejected before child declaration is accepted
2. if a child collection exists and is parseable as a sequence, `declared_fanout = len(children)`
3. otherwise, `declared_fanout = null`
4. `accepted_fanout = 0`
5. `controller_child` event count must be `0`

If `controller.max_fanout_exceeded` occurs:
1. the error occurs during envelope validation
2. `declared_fanout = raw envelope child count`
3. `accepted_fanout = 0`
4. `controller_child` event count must be `0`

If the envelope is accepted:
1. `controller_child` event count must equal `accepted_fanout`

The envelope-invalid and max-fanout-exceeded cases are the only exceptions to the accepted-envelope child event rule.

### 6.7 Canonical Field Order for controller_child

`controller_child` payload fields must serialize in exactly this order:
1. `event`
2. `run_id`
3. `child_index`
4. `execution_order`
5. `child_workload`
6. `status`
7. `requested_timeout`
8. `enforced_timeout`
9. `error_code`

### 6.8 Example

```json
{
  "event": "controller_child",
  "run_id": "run_42",
  "child_index": 3,
  "execution_order": 3,
  "child_workload": "compile_artifact",
  "status": "not_attempted",
  "requested_timeout": 300,
  "enforced_timeout": null,
  "error_code": null
}
```

## 7. Observability Failure Policy

Observability emission, canonicalization, and schema validation are contract-authoritative in V1.

If required observability events cannot be canonicalized, validated, or emitted:
1. controller execution must fail closed
2. the controller run result must be `failed`
3. the controller run `error_code` must be `controller.observability_emit_failed`

Stable error code for this contract:
`controller.observability_emit_failed`

The runtime must not continue silently and must not downgrade this condition to best-effort telemetry.

### 7.1 Observability Failure Rule

If observability canonicalization, schema validation, or event emission fails, the controller run fails closed with:
1. `result = "failed"`
2. `error_code = "controller.observability_emit_failed"`

The final run-level provenance summary must record this failure.

Previously recorded child provenance entries remain unchanged and must not be rewritten.

### 7.2 Observability Batch Emission Atomicity

Observability V1 uses `post_execution_batch_emit`.

Emission is atomic at the run level.

Either:
1. the complete canonical event batch is validated and emitted
or
2. no events are emitted and the run fails closed with `controller.observability_emit_failed`

Partial event streams are forbidden.

## 8. Observability vs Provenance

Observability events are operational telemetry and do not replace or modify provenance records.

They must not:
1. replace provenance records
2. mutate prior child provenance artifacts
3. introduce execution state not present in provenance

Provenance remains the authoritative deterministic execution record defined in `CONTROLLER_WORKLOAD_V1.md`.

Observability exists to support:
1. operator debugging
2. telemetry pipelines
3. runtime monitoring
4. replay correlation

## 9. Provenance Correlation Contract

`child_index` is the zero-based positional index of the child workload in the accepted controller envelope.

Provenance child records must correlate using this index.

If provenance does not store an explicit index field, the positional order of child records is authoritative and must equal `child_index`.

Deterministic correlation keys:

| Surface | Correlation Key |
|---|---|
| controller run | `run_id` |
| child execution | `run_id + child_index` |
| provenance artifacts | `run_id plus positional child index` |

This enables deterministic linking between:

runtime execution
↓
provenance artifacts
↓
observability telemetry

## 10. Determinism Requirements

Observability output must obey:
1. event ordering equals runtime execution ordering
2. canonical serialization rules defined in `CONTROLLER_WORKLOAD_V1.md`
3. equivalent inputs produce identical ordered event payloads after canonical comparison projection
4. event fields must be serialized in canonical key order
5. implementations must not rely on runtime dictionary ordering

### 10.1 Canonical Comparison Projection

Deterministic event-stream equality comparisons must compare canonical event payloads after removing the `run_id` field from each event object.

Excluded fields:
1. `run_id`

Included fields:
1. all other fields defined by this specification

No other event fields are excluded in V1.

## 11. Volatile Timing Fields Policy

Wall-clock timestamps, duration measurements, queue latency, and other volatile timing metadata are out of scope for V1 canonical observability events.

Such fields must not appear in canonical observability payloads.

If introduced later, they must either:
1. be excluded from canonical determinism comparisons
or
2. exist in a separate non-canonical telemetry surface

## 12. Deterministic Event Stream Shape

For accepted envelopes, the deterministic event stream shape is:
`1 + accepted_fanout`

That is:
1. one `controller_run` event
2. one `controller_child` event for each declared child in the accepted envelope

Example deterministic stream:
1. `controller_run`
2. `controller_child index=0 success`
3. `controller_child index=1 success`
4. `controller_child index=2 failure`
5. `controller_child index=3 not_attempted`
6. `controller_child index=4 not_attempted`

For `controller.envelope_invalid`, the deterministic event stream is:
1. `controller_run`
2. child event count is `0`

For `controller.max_fanout_exceeded`, the deterministic event stream is:
1. `controller_run`
2. child event count is `0`

For `controller.disabled_by_policy`, the deterministic event stream is:
1. `controller_run`
2. child event count is `0`

## 13. Test Requirements

### 13.1 Contract Tests

Validate:
1. event schema
2. required fields
3. allowed enumerations
4. canonical field ordering
5. accepted-envelope child event count rule
6. envelope-invalid zero-child-event exception
7. max-fanout-exceeded zero-child-event exception

### 13.2 Unit Tests

Validate:
1. event emission ordering
2. serialization stability
3. error-code propagation
4. not_attempted field semantics
5. blocked vs failed result mapping
6. exclusion of run_id from deterministic comparisons
7. run-level atomic batch emission behavior
8. child failure error_code assignment rules
9. declared_fanout and accepted_fanout semantics
10. blocked run invariant
11. result/error invariants

### 13.3 Integration Tests

Execute controller workloads and verify:
1. `controller_run` emits before all child events
2. child events align with provenance ordering
3. accepted-envelope child event count equals `accepted_fanout`
4. invalid-envelope child event count equals zero
5. max-fanout-exceeded child event count equals zero
6. equivalent inputs produce identical event streams after canonical comparison projection
7. observability emission failure fails closed with `controller.observability_emit_failed`
8. no partial observability batch is emitted on emission failure
9. if any child event has `status = "success"`, run result is not blocked

## 14. Schema Authority Artifact

A machine-checkable schema companion artifact is required:
`schemas/controller_observability_v1.json`

Authority model:

| Artifact | Authority |
|---|---|
| `docs/specs/CONTROLLER_OBSERVABILITY_V1.md` | semantic contract |
| `schemas/controller_observability_v1.json` | structural validation |

The schema artifact must exist and must encode, at minimum:
1. `declared_fanout` as integer or null
2. `accepted_fanout` as non-negative integer
3. allowed result enumeration
4. allowed status enumeration
5. required fields and field types for both event kinds

Contract tests must validate observability payloads against the schema artifact.

## 15. Non-Goals

This specification does not define:
1. metrics aggregation
2. monitoring dashboards
3. alerting rules
4. telemetry transport protocols
5. volatile timing metadata in canonical payloads

These concerns belong to operational infrastructure layers.

## 16. Recommended Helper Module

Implementation should provide a helper module:
`orket/extensions/controller_observability.py`

Recommended responsibilities:
1. `emit_controller_run(...)`
2. `emit_controller_child(...)`
3. `validate_observability_schema(...)`
4. `canonicalize_event(...)`

`emit_controller_run()` must execute before any `controller_child` event is emitted.

## 17. Resulting Controller Architecture

```
docs/specs/
    CONTROLLER_WORKLOAD_V1.md
    CONTROLLER_OBSERVABILITY_V1.md

schemas/
    controller_observability_v1.json

docs/projects/archive/controller-workload/
    CW03082026-Phase2D/
        04-REQUIREMENTS-Phase-2D.md
        05-IMPLEMENTATION-PLAN-Phase-2D.md
        06-RELIABILITY-HARDENING-Phase-2D.md
        07-V1-PLANNING-HANDOFF.md

docs/runbooks/
    controller-workload-operator.md

docs/guides/
    controller-workload-authoring.md
```

This preserves clear separation between:
1. runtime semantics
2. telemetry contract
3. operational procedures
