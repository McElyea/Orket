# Runtime Invariants

Last updated: 2026-03-06  
Status: Active (governance contract)  
Owner: Orket Core

## Purpose

Define non-negotiable runtime rules that must remain true across all workloads, tools, and compatibility surfaces.

## Invariants

1. Tool calls must be ledger-recorded before execution begins.
2. Tool execution must occur only through canonical tool dispatch; workloads cannot bypass dispatch.
3. Every emitted artifact must have a registered schema version in `core/artifacts/schema_registry.yaml`.
4. Every tool invocation must emit `tool_invocation_manifest.json` with ring, schema version, determinism class, capability profile, and tool contract version.
5. Ring policy violations (`core`, `compatibility`, `experimental`) must fail closed before tool execution.
6. Compatibility mappings may expand only to `core` tools and must not chain to other compatibility mappings.
7. Compatibility mappings must not elevate determinism class relative to composed core tools.
8. Replay mode must bypass model inference, prompt construction, and repair heuristics; replay uses recorded tool calls only.
9. Deterministic replay is required for deterministic runs and deterministic compatibility mappings.
10. All runtime/tool error codes must be machine-readable and `snake_case`.
11. Workload failures must not crash the core runtime process.
12. Any runtime degradation mode must be explicit in operator-visible and machine-assertable outputs.

## Determinism Rules

1. Canonical ordering: `pure > workspace > external`.
2. Tool-level determinism is declared in tool contracts.
3. Run-level determinism resolves to the least-deterministic invoked tool class.
4. Mapping-level determinism resolves to the least-deterministic mapped core tool class.

## Verification Expectations

1. Golden run harness must include `runtime_contract_hash` and `tool_registry_version`.
2. Promotion from compatibility to core requires replay and parity gates with no unresolved drift classifications.
3. Invariant violations must be treated as contract failures, not soft warnings.
