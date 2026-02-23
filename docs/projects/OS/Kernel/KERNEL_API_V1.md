# Orket Kernel API v1 (Draft)

Last updated: 2026-02-22
Status: Draft (ideas -> candidate active plan)
Owner: Orket Core

## 1) Goal
Define a minimal, stable Kernel API for Orket as an OS-class substrate for agentic systems.

Kernel API v1 is intentionally small:
1. Run lifecycle control
2. Deterministic event logging
3. Contract-safe state transitions
4. Capability and permission checks
5. State-backed link integrity
6. Replay and equivalence checks

Everything else is a subsystem/plugin behind this API.

## 2) Kernel API Surface (v1)

### 2.1 Run Control
`start_run(request) -> run_handle`
1. Creates run envelope (`run_id`, workflow identity, policy/model profile refs).
2. Binds visibility mode and snapshot semantics.

`execute_turn(run_handle, turn_input) -> turn_result`
1. Runs one deterministic turn through the stage pipeline.
2. Emits stage events and outcome descriptors.

`finish_run(run_handle, outcome) -> run_summary`
1. Finalizes run status and flushes state artifacts.
2. Applies or discards buffered state per policy.

### 2.2 Event and Trace
`emit_event(event)`
1. Single-line machine-parseable log emission.
2. Contracted stage/code/location semantics.

`write_trace_artifacts(run_handle, trace_bundle)`
1. Writes deterministic trace artifacts for replay/audit.
2. Must include schema/version metadata.

### 2.3 State and Integrity
`validate_triplet(triplet) -> validation_report`
1. Validates body/links/manifest via fixed stage order.
2. Rejects invalid transitions in fail-closed mode.

`validate_links_against_index(triplet, sovereign_index) -> integrity_report`
1. Enforces non-orphan link invariants.
2. Supports local-batch exceptions for same-batch IDs.

### 2.4 Capability and Permissions
`authorize_tool_call(context, tool_request) -> decision`
1. Verifies declared permissions vs requested permissions.
2. Denies undeclared side effects.

`resolve_capability(role, task) -> capability_plan`
1. Maps work to allowed role/model/tool capabilities.
2. Produces auditable decision records.

### 2.5 Replay and Equivalence
`replay_run(run_descriptor) -> replay_result`
1. Replays deterministic execution path under pinned config.
2. Emits parity diagnostics on divergence.

`compare_runs(run_a, run_b, contract_version) -> equivalence_report`
1. Structural/behavioral equivalence (not semantic intent).
2. Deterministic pass/fail reasons.

## 3) Kernel Invariants (Non-Negotiable)
1. Stage pipeline is exactly:
`base_shape -> dto_links -> relationship_vocabulary -> policy -> determinism`
2. Fail-closed diffing: unknown diff state is failure.
3. Logs are deterministic and single-line safe.
4. State integrity checks run before promotion/commit.
5. Plugin behavior is allowlisted and schema-validated.
6. Contract versions are explicit and logged.

## 4) Mapping to Current Code

### 4.1 What exists now
1. Triplet validation kernel (stage pipeline):
`tools/ci/orket_sentinel.py`
2. Deterministic logging with v1/v2 payload contract:
`tools/ci/orket_sentinel.py`
3. Explicit plugin registry + schema-validated plugin events:
`tools/ci/orket_sentinel.py`
4. Related-stem extraction for connectivity:
`tools/ci/orket_sentinel.py` (`related_stems` plugin)
5. State-backed orphan-link validation:
`tools/ci/orket_sentinel.py` (`orphan_links` plugin)
6. Fire-drill fixture harness:
`tools/ci/test_sentinel.py`, `tools/ci/fixtures/`
7. Visualization observer:
`tools/ci/orket_map.py`

### 4.2 What is partial
1. Replay/equivalence is partially represented by docs + scripts but not exposed as a single Kernel API.
2. Capability/permission authorization exists in broader runtime areas but is not consolidated as a frozen kernel interface.
3. Snapshot/commit semantics are designed and tested in parts, but not surfaced as a first-class kernel module boundary.

### 4.3 What is missing
1. Stable Python module/package for Kernel API (for example `orket/kernel/v1/...`).
2. Formal request/response DTOs for kernel calls.
3. Versioned compatibility layer for kernel evolution (`v1` -> `v2` migration policy).
4. Unified run-level API that composes CI validator behavior with runtime orchestration behavior.
5. Contract tests that assert kernel API compatibility independent of implementation internals.

## 5) Gap List (Priority-Ordered)

### Gap A (P0): Kernel module boundary
Problem:
Kernel logic is implemented but centered in CI tooling, not a runtime kernel package.

Target:
1. Create `orket/kernel/v1/` with stable interfaces.
2. Keep current sentinel as adapter/wrapper, not source of kernel truth.

### Gap B (P0): Typed API contracts
Problem:
No frozen typed API for `start_run/execute_turn/finish_run/replay/compare`.

Target:
1. Add typed kernel DTOs.
2. Add schema/version fields in every request/response.

### Gap C (P1): Capability authorization as kernel primitive
Problem:
Permission and capability checks are not exposed as a kernel API call.

Target:
1. Introduce `authorize_tool_call` and `resolve_capability` kernel contracts.
2. Enforce deterministic failure codes for denied actions.

### Gap D (P1): Run-level determinism comparator
Problem:
Current comparator behavior is scattered across scripts/tests.

Target:
1. Add `compare_runs` kernel API with standardized report shape.
2. Pin deterministic diagnostics and compatibility expectations.

### Gap E (P2): Plugin contract hardening lifecycle
Problem:
Plugin schema checks exist but no formal plugin API versioning policy.

Target:
1. Introduce plugin API version field and compatibility checks.
2. Add deny-by-default behavior for unknown plugin API versions.

## 6) First Implementation Slice (Recommended)
1. Define `orket/kernel/v1/contracts.py` with API DTOs and call signatures.
2. Refactor sentinel stage engine into reusable kernel validator service.
3. Keep `tools/ci/orket_sentinel.py` as thin CLI adapter.
4. Add kernel compatibility tests:
`tests/contracts/test_kernel_api_v1.py`
5. Add migration note documenting adapter compatibility guarantees.

## 7) Out of Scope for v1
1. Full distributed scheduler/runtime re-architecture.
2. Vendor-specific optimization in kernel API.
3. Semantic equivalence scoring in determinism comparator.
4. UI/graph rendering framework decisions.
