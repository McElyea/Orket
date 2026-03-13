# Runtime Invariants

Last updated: 2026-03-13  
Status: Active (governance contract)  
Owner: Orket Core

## Purpose

Define non-negotiable runtime rules that must remain true across all workloads, tools, and compatibility surfaces.

## Invariants

1. `INV-001`: Tool calls must be ledger-recorded before execution begins.
2. `INV-002`: All tool execution must occur through canonical dispatcher invocation. Tool implementations must not be imported and executed directly by workloads, adapters, or compatibility mappings.
3. `INV-003`: Tools must not invoke other tools directly. Composition must occur through workload orchestration or compatibility mapping via dispatcher.
4. `INV-004`: Every emitted artifact must have a registered schema version in `core/artifacts/schema_registry.yaml`.
5. `INV-005`: Artifact-ledger referential integrity is mandatory:
   1. every emitted `artifact_id` must appear in a ledger event
   2. ledger artifact references must resolve to existing artifacts
   3. ledger artifact references must include `artifact_hash` captured at emission (`sha256(artifact_bytes)`)
6. `INV-006`: Every tool invocation must record normalized `tool_invocation_manifest` evidence with ring, schema version, determinism class, capability profile, and tool contract version.
7. `INV-007`: Ring policy violations (`core`, `compatibility`, `experimental`) must fail closed before tool execution.
8. `INV-008`: Capability profile violations must fail closed before tool execution.
9. `INV-009`: Compatibility mappings may expand only to `core` tools, must not chain to compatibility mappings, and must not elevate determinism class.
10. `INV-010`: Replay mode must bypass model inference, prompt construction, repair heuristics, and tool-validator repair paths; replay uses recorded tool calls only.
11. `INV-011`: Replay completeness is required before execution. Replay must fail closed when required tool-call, tool-result, or `tool_invocation_manifest` evidence is missing.
12. `INV-012`: Deterministic replay is required for deterministic runs and deterministic compatibility mappings.
13. `INV-013`: All runtime/tool error codes must be machine-readable and `snake_case`.
14. `INV-014`: Workload failures must not crash the core runtime process.
15. `INV-015`: Any runtime degradation mode must be explicit in operator-visible and machine-assertable outputs.
16. `INV-016`: Tool registry snapshots must be immutable for the full run duration.
17. `INV-017`: Artifact schema snapshots must be immutable for the full run duration.
18. `INV-018`: `runtime_contract_hash` must remain immutable for the full run duration.
19. `INV-019`: Capability profile snapshot must remain immutable for the full run duration.
20. `INV-020`: Replay must verify compatibility of tool registry snapshot, runtime contract hash, artifact schema snapshot, and capability profile snapshot before execution.
21. `INV-021`: Mutable runtime state must be scoped by `run_id`; cross-run mutable sharing is forbidden.
22. `INV-022`: Runtime must track tool invocation count per run and enforce `max_tool_invocations_per_run` (default `200`); execution must fail closed when exceeded.
23. `INV-023`: If a tool declares `determinism_class = pure` but produces observable side effects, runtime must emit `determinism_violation`.
24. `INV-024`: Ledger ordering must be monotonic:
   1. `sequence_number` strictly increases within a run
   2. event timestamps must not move backwards.
25. `INV-025`: Ledger events must include `ledger_schema_version`, and that version must be compatible with the active runtime contract.
26. `INV-026`: Artifacts must not be emitted before the corresponding `tool_result` ledger event is recorded.
27. `INV-027`: Artifact schema versions referenced by emitted artifacts must exist in the active artifact schema snapshot and must not change during run execution.
28. `INV-028`: Every `tool_call` ledger event must have a corresponding `tool_result` ledger event with matching `run_id` and `tool_name`; `tool_result` must reference the originating call via `call_sequence_number`.
29. `INV-029`: Run identity (`run_id`, workload identity, start timestamp) must remain immutable for the full run duration.
30. `INV-030`: Tool contract definitions referenced by a run must remain immutable for the run duration and must match the tool registry snapshot used at run start.
31. `INV-031`: `capability_manifest.json` must match the capability profile snapshot captured at run start and must remain immutable for the run duration.
32. `INV-032`: Artifacts emitted during a run must be immutable. Post-emission mutation or overwrite of artifacts referenced by ledger events is forbidden.
33. `INV-033`: Tool implementations must be idempotent for identical invocation manifests unless declared `determinism_class = external`; duplicate non-external invocation hashes must be rejected unless runtime is explicitly configured for deterministic deduplication.
34. `INV-034`: Ledger ordering must be derived solely from `sequence_number`. Timestamp fields are informational and must not be used for execution ordering.
35. `INV-035`: Replay execution must not perform side effects outside artifact reconstruction and ledger validation. Adapters and tools must operate in replay-safe mode.
36. `INV-036`: Runs invoking tools with `determinism_class = workspace` must capture `workspace_state_snapshot` at run start. Replay must fail closed when workspace compatibility checks fail.
37. `INV-037`: Runtime initialization must fail closed if tool registry snapshot, artifact schema snapshot, compatibility map schema, or tool contract snapshot fail validation against their declared schemas.

## Execution Ordering

1. `ledger.record(tool_call)`
2. Tool execution
3. `ledger.record(tool_result)`
4. Artifact emission

## Determinism Rules

1. Canonical ordering: `pure > workspace > external`.
2. Tool-level determinism is declared in tool contracts.
3. Run-level determinism resolves to the least-deterministic invoked tool class.
4. Mapping-level determinism resolves to the least-deterministic mapped core tool class.

## Verification Expectations

1. Protocol replay evidence must include `runtime_contract_hash`, `tool_registry_version`, and artifact schema snapshot version.
2. Promotion from compatibility to core requires replay and parity gates with no unresolved drift classifications.
3. Invariant violations must be treated as contract failures, not soft warnings.
4. Replay and scoreboard systems must fail closed on incomplete evidence.
