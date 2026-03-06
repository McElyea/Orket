# Core Runtime Requirements Implementation Plan

Last updated: 2026-03-06  
Status: Active (implementation planning)  
Owner: Orket Core

## Purpose

Define how to implement the core runtime requirements and invariants currently specified in:
1. `runtime_invariants.md`
2. `runtime_stability_focus_requirements.md`
3. `core_tool_rings_compatibility_requirements.md`
4. `tool_contract_template.md`

## Slicing Strategy Decision

Decision: **vertical-first slices with a thin horizontal bootstrap**.

Rationale:
1. Vertical slices give production-like proof early (behavior + artifacts + tests together).
2. Pure horizontal layering would delay replay and determinism evidence until too late.
3. A small bootstrap slice is still required to prevent duplicate contract definitions.
4. This strategy reduces false-green risk by closing each slice with explicit runtime proof.

## Delivery Model

1. Slice IDs: `CORE-IMP-00` to `CORE-IMP-07`.
2. Each slice must ship:
   1. minimal code changes for the claimed behavior
   2. contract/integration tests at the highest practical layer
   3. updated artifacts/telemetry where required
   4. explicit closeout note (what is proven vs not proven)
3. No slice may weaken runtime invariants.

## Phase Overview

1. Phase 0 (bootstrap): `CORE-IMP-00`
2. Phase 1 (deterministic run spine): `CORE-IMP-01` and `CORE-IMP-02`
3. Phase 2 (governance enforcement): `CORE-IMP-03` and `CORE-IMP-04`
4. Phase 3 (reliability and promotion controls): `CORE-IMP-05` and `CORE-IMP-06`
5. Phase 4 (compatibility pilot): `CORE-IMP-07`
6. Phase 5 (future graph reconstruction): `CORE-IMP-08` (post-`CORE-IMP-07`)

## Slices

### CORE-IMP-00: Contract Bootstrap (Horizontal Foundation)

Scope:
1. Establish canonical locations and loaders for:
   1. artifact schema registry (`core/artifacts/schema_registry.yaml`)
   2. compatibility surface map (`core/tools/compatibility_map.yaml`)
   3. tool registry snapshot version source
2. Add schema/version parsing utilities shared by runtime and replay flows.
3. Capture immutable tool registry snapshot at runtime start.
4. Capture immutable artifact schema registry snapshot at runtime start.
5. Define and validate compatibility surface map schema.
6. Capture immutable tool contract snapshot bound to the active tool registry snapshot.

Deliverables:
1. Registry files and loader modules with strict validation.
2. Startup/runtime failure paths for missing or malformed contracts.
3. `tool_registry_snapshot.json`.
4. `artifact_schema_snapshot.json`.
5. `compatibility_map_schema.yaml`.
6. `tool_contract_snapshot.json`.

Tool registry snapshot example:
```json
{
  "tool_registry_version": "1.2.0",
  "tools": ["file.patch", "workspace.search"]
}
```

Artifact schema snapshot example:
```json
{
  "artifact_schema_registry_version": "1.0",
  "artifacts": ["run.json", "tool_call.json", "tool_result.json", "run_summary.json"]
}
```

Required proof:
1. Unit tests for schema registry and compatibility map parsing.
2. Contract tests for failure-closed behavior on invalid registry documents.

Exit criteria:
1. No runtime path reads ad-hoc contract definitions outside canonical locations.

### CORE-IMP-01: Deterministic Run Spine

Scope:
1. Enforce execution ordering:
   1. `ledger.record(tool_call)`
   2. tool execution
   3. `ledger.record(tool_result)`
   4. artifact emission
2. Require `tool_invocation_manifest.json` for every invocation.
3. Emit `run_determinism_class` and `capability_manifest.json`.
4. Enforce `max_tool_invocations_per_run` guard (default `200`).
5. Enforce run-scoped mutable runtime state isolation by `run_id`.
6. Enforce artifact-ledger referential integrity at write time.
7. Enforce `run_identity` immutability for full run duration.
8. Enforce strict tool call/result pairing and forbid orphaned `tool_call` events.
9. Enforce `capability_manifest.json` integrity against run-start capability snapshot and immutability.

Deliverables:
1. Runtime instrumentation hooks for deterministic ordering.
2. Manifest generation integrated into run lifecycle.
3. `run_identity.json`.
4. `ledger_event_schema.json`.
5. `capability_manifest_schema.json`.

Run identity example:
```json
{
  "run_id": "r-4821",
  "workload": "localclaw",
  "start_time": "2026-03-06T14:22:31Z"
}
```

Ledger event schema minimum fields:
1. `ledger_schema_version`
2. `event_type`
3. `timestamp`
4. `tool_name`
5. `run_id`
6. `sequence_number`
7. `call_sequence_number` (required on `tool_result` events)

Ledger event schema example:
```json
{
  "ledger_schema_version": "1.0",
  "event_type": "tool_call",
  "run_id": "r-4821",
  "sequence_number": 14
}
```

Required proof:
1. Integration test asserting ledger order on successful and failing tool calls.
2. Contract tests asserting required invocation manifest fields.
3. Integration test asserting run-level determinism classification.
4. Concurrency test asserting ledger ordering remains correct under parallel tool invocation attempts.
5. Contract tests for monotonic `sequence_number` and non-backwards timestamps.
6. Contract tests for artifact-ledger referential integrity enforcement.
7. Contract test for `max_tool_invocations_per_run` fail-closed behavior.
8. Integration tests proving run-scoped mutable-state isolation.
9. Contract tests asserting `tool_call` to `tool_result` pairing with `call_sequence_number`.
10. Integration tests asserting artifact emission occurs only after matching `tool_result` is recorded.
11. Contract tests asserting `run_identity` immutability.
12. Contract tests asserting `capability_manifest.json` matches run-start snapshot and remains immutable.

Exit criteria:
1. Runs cannot complete without required invocation manifests.
2. Ledger order contract is mechanically enforced.

### CORE-IMP-02: Golden Replay Integrity

Scope:
1. Implement `runtime_contract_hash` generation from required contract surfaces.
2. Persist `tool_registry_version` and runtime hash with golden metadata.
3. Enforce replay-mode behavior:
   1. no inference
   2. no prompt construction
   3. no repair heuristics or tool-validator repair paths
   4. recorded tool calls only
4. Add replay compatibility checks for:
   1. tool registry snapshot
   2. runtime contract hash
   3. artifact schema registry version
   4. capability profile snapshot
5. Validate replay completeness for required artifacts before execution.
6. Implement drift classifier priority ordering.
7. Record runtime policy versions and include them in replay metadata and runtime contract hash inputs.
8. Validate replay compatibility against `ledger_schema_version`.

Deliverables:
1. Runtime/replay hash computation utility.
2. Golden run metadata schema update.
3. Drift classifier with deterministic layer precedence.
4. `drift_report.json` includes `drift_schema_version`.
5. `runtime_policy_versions.json`.

Drift schema example:
```json
{
  "drift_schema_version": "1.0"
}
```

Runtime policy versions example:
```json
{
  "prompt_budget_policy": "1.0",
  "retry_policy": "1.1",
  "promotion_gate_policy": "1.0"
}
```

Required proof:
1. Integration replay test proving inference path is never called.
2. Contract tests for compatibility rejection on mismatched hashes/versions.
3. Drift-classifier tests validating priority order.
4. Replay completeness tests fail closed when required artifacts are missing.
5. Replay compatibility tests fail closed on incompatible `ledger_schema_version`.

Exit criteria:
1. Replay fails closed on incompatible runtime contracts.
2. Drift layers are classified in deterministic order.

### CORE-IMP-03: Ring Policy Enforcement

Scope:
1. Static enforcement preventing compatibility/experimental imports of core internals.
2. Runtime ring-policy enforcement in tool dispatch.
3. Reject undeclared tools and ring violations before execution.
4. Validate active capability profile against tool capability requirements before execution.
5. Validate tool determinism class compatibility with active run determinism policy.
6. Enforce tool invocation boundary (`tool -> tool` direct calls forbidden).
7. Verify determinism declarations at runtime and emit `determinism_violation` on violations.

Deliverables:
1. Lint/static-check rule for import boundaries.
2. Runtime policy guard in dispatcher.

Required proof:
1. Static-rule tests for forbidden import paths.
2. Integration tests asserting pre-execution rejection semantics.
3. Integration tests asserting tool-to-tool direct invocation rejection.
4. Contract tests asserting `determinism_violation` emission when pure tools produce side effects.

Exit criteria:
1. Ring boundary violations are impossible to execute silently.

### CORE-IMP-04: Compatibility Mapping Governance

Scope:
1. Enforce mapping constraints:
   1. expands to core tools only
   2. no compatibility chaining
   3. determinism propagation (least-deterministic wins)
   4. deterministic translation for identical inputs
2. Require mapping metadata:
   1. mapping version
   2. schema compatibility range
   3. determinism class
3. Emit `compat_translation.json`.

Deliverables:
1. Compatibility map validator and dispatcher integration.
2. Translation artifact emission path.
3. `compat_translation.json` includes `mapping_version` and `mapping_determinism`.

Compatibility translation example:
```json
{
  "compat_tool": "openclaw.file_edit",
  "mapping_version": 1,
  "mapping_determinism": "workspace"
}
```

Required proof:
1. Contract tests for mapping validation and deterministic class propagation.
2. Integration tests for translation artifact generation.
3. Contract test asserting translation determinism for identical inputs.

Exit criteria:
1. Invalid compatibility mappings fail at load-time or pre-dispatch.

### CORE-IMP-05: Prompt Budget and Tokenizer Truth

Dependencies:
1. `CORE-IMP-01`
2. `CORE-IMP-02`

Scope:
1. Implement stage-level prompt budgets and fail-closed enforcement.
2. Bind token accounting to active backend tokenizer.
3. Emit `prompt_budget_usage.json` and prompt structural diffs.
4. Emit `prompt_structure.json` with prompt/template/tokenizer/budget policy versions.

Deliverables:
1. Prompt budget engine with stage-aware limits.
2. Backend tokenizer adapter contract.
3. `prompt_structure.json`.

Prompt structure example:
```json
{
  "prompt_template_version": "1.0",
  "tokenizer_id": "qwen2-tokenizer",
  "budget_policy_version": "1.0"
}
```

Required proof:
1. Contract tests for budget exceed fail-closed semantics.
2. Integration tests for backend-tokenizer accounting path.

Exit criteria:
1. Prompt budget decisions are deterministic for a given model backend.

### CORE-IMP-06: Reliability Scoreboard and Promotion Gates

Scope:
1. Build scoreboard pipeline from ledger records only.
2. Enforce rolling window policy (1000 invocations or 30 days default).
3. Implement promotion gate evaluator:
   1. reliability threshold
   2. replay across configured `N` golden runs
   3. no unresolved drift classifications
4. Define artifact retention tiers for long-lived evidence management.

Deliverables:
1. Scoreboard computation module and artifact output.
2. Promotion gate evaluator utility.
3. `tool_scoreboard.json` includes `scoreboard_schema_version` and `scoreboard_policy_version`.
4. `artifact_retention_tiers.yaml`.

Scoreboard schema example:
```json
{
  "scoreboard_schema_version": "1.0",
  "scoreboard_policy_version": "1.0",
  "tool": "file.patch",
  "success_rate": 0.97
}
```

Artifact retention tiers example:
```yaml
tier_1:
  - run_summary.json
tier_2:
  - tool_call.json
  - tool_result.json
  - tool_invocation_manifest.json
tier_3:
  - tool_debug_trace.json
  - compat_latency_profile.json
```

Required proof:
1. Contract tests proving scoreboard reproducibility from ledger only.
2. Integration tests for promotion-gate pass/fail outcomes.
3. Scoreboard generation fails closed on incomplete ledger coverage (for example missing `tool_result` event).

Exit criteria:
1. Promotion decision can be reproduced from stored evidence.

### CORE-IMP-07: Compatibility Pilot Vertical Slice

Scope:
1. Implement a small reference compatibility set (2-3 mappings) from `core/tools/compatibility_map.yaml`.
2. Execute golden parity runs in live and replay modes.
3. Validate end-to-end observability artifacts for compatibility calls.

Deliverables:
1. Reference compatibility mappings and fixtures.
2. Parity run evidence artifacts.
3. `compat_latency_profile.json`.

Compatibility latency example:
```json
{
  "compat_tool": "openclaw.file_edit",
  "core_tools_used": ["workspace.search", "file.patch"],
  "latency_ms": 82
}
```

Required proof:
1. Golden parity tests for pilot mappings.
2. Replay parity for deterministic mappings and classified nondeterministic behavior for external mappings.

Exit criteria:
1. At least one compatibility mapping meets all promotion prerequisites (not necessarily promoted).

### CORE-IMP-08: Run Graph Reconstruction (Future Slice)

Status:
1. Future slice (`P2-P3`) executed after `CORE-IMP-07`.

Goal:
1. Deterministically reconstruct a run DAG from ledger events and artifacts for debugging, lineage, and replay analysis.

Scope:
1. Build deterministic graph reconstruction engine from ledger + artifacts.
2. Define graph schema with node and edge types.
3. Emit derived `run_graph.json` artifact.
4. Ensure graph parity between live and replay for deterministic runs.
5. Enforce rule: ledger is source of truth, graph is derived only.

Node types:
1. `tool_call`
2. `compat_mapping`
3. `workload_stage`
4. `artifact`

Edge types:
1. `call_result`
2. `artifact_produced`
3. `compat_expansion`
4. `execution_order`

Deliverables:
1. `run_graph_schema.json`.
2. `run_graph.json`.
3. graph reconstruction engine module.

Required proof:
1. Contract test for graph reproducibility (same ledger/artifacts -> same graph).
2. Contract test for graph determinism and idempotency.
3. Contract test for artifact-lineage integrity.
4. Contract test for compatibility-expansion edge correctness.
5. Integration test for golden run graph reconstruction.
6. Integration test for live vs replay graph parity on deterministic runs.

Exit criteria:
1. `run_graph.json` is fully derivable from ledger + artifacts.
2. Graph output is deterministic and version-compatible.
3. No graph path becomes a primary truth source.

## Cross-Cutting Test Policy

1. Highest practical proof layer is required for runtime claims.
2. Unit-only proof is insufficient for dispatch, replay, and ledger ordering invariants.
3. Mock-heavy tests may exist for edge isolation but cannot be cited as runtime truth proof.

## Risk Register (Execution-Blocking Risks)

1. Existing runtime paths may bypass canonical dispatcher.
2. Current ledger event model may be insufficient for strict ordering assertions.
3. Replay path may currently rely on prompt/model helpers.
4. Scoreboard code may currently depend on non-ledger telemetry.
5. Artifact emission paths may bypass schema-registry validation.
6. Tool registry snapshot may include tools incompatible with active capability profile.
7. Golden fixtures may become stale relative to tool-registry evolution.
8. Cross-run mutable runtime state leakage may invalidate replay guarantees.

Mitigation:
1. Detect and patch bypasses during `CORE-IMP-01` and `CORE-IMP-03`.
2. Add invariant tests before broader refactors.
3. Keep slices small and gate each slice before proceeding.
4. Centralize artifact emission through `record_artifact()`.
5. Validate registry snapshot against capability profile at run start.
6. Record `tool_registry_version` in golden fixtures and fail closed on mismatch.
7. Enforce run-scoped mutable state boundaries in runtime adapters and caches.

## Definition of Done (Program Level)

1. All invariants in `runtime_invariants.md` are implemented and enforced.
2. Focus Items 1-7 have executable contract tests and integration proof.
3. Replay compatibility checks prevent silent divergence.
4. Scoreboard and promotion decisions are ledger-auditable.
