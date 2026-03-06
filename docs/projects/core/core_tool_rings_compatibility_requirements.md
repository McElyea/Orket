# Core Tool Rings + Compatibility Contract Requirements

Last updated: 2026-03-06  
Status: Active (requirements draft)  
Owner: Orket Core

## Purpose

Define the requirements for a tool architecture that preserves deterministic core behavior while allowing OpenClaw-level capability coverage through a compatibility surface.

## Scope

In scope:
1. Tool ring model (`core`, `compatibility`, `experimental`).
2. Compatibility mapping contract (`openclaw_tool` -> `orket_tool` or sequence).
3. Reliability, observability, and proof requirements per ring.

Out of scope:
1. Concrete implementation plan/sprints.
2. Immediate expansion of all compatibility tools.
3. Non-tool runtime architecture changes unrelated to ring boundaries.

## Focus Item 7: Tool Rings + Compatibility Contract

### Goal

Support OpenClaw-class capability breadth without sacrificing core runtime determinism.

### Related Items

1. Define core tools baseline.
2. Tool sandbox/capability profiles.
3. Tool validator and structured error contract.
4. Tool reliability scoreboard.
5. Golden run harness and deterministic replay.

### Requirements

Behavior:
1. Ring `core` contains deterministic baseline tools and is the only ring required for runtime validity.
2. Ring `compatibility` exposes OpenClaw-equivalent capabilities through mapped contracts, not direct core bypass.
3. Ring `experimental` remains workload-scoped and cannot become implicit runtime dependency.
4. Every tool must declare:
   1. determinism class (`pure`, `workspace`, `external`)
   2. side-effect class (`none`, `workspace_mutation`, `external_mutation`)
   3. timeout policy
   4. retry policy
5. Compatibility tools may compose core tools, but must preserve observable contract semantics.
6. Unsupported compatibility calls fail closed with stable, machine-readable errors.

Interfaces:
1. Tool registry entries must include:
   1. `tool_name`
   2. `ring`
   3. `schema_version`
   4. `input_schema`
   5. `output_schema`
   6. `error_schema`
   7. `capability_profile`
2. Compatibility map must define:
   1. `compat_tool_name`
   2. `mapped_core_tools`
   3. `semantic_notes`
   4. `parity_constraints`
3. Runtime tool dispatch must reject undeclared or ring-violating tools before execution.

Observability:
1. Each run must record:
   1. tool ring used for each invocation
   2. compatibility mapping id/version when applicable
   3. tool schema version
2. Standard artifacts:
   1. `tool_call.json`
   2. `tool_result.json`
   3. `tool_metrics.json`
   4. `tool_ring_manifest.json`
3. Violations emit explicit artifacts/events with stable error codes.

Failure semantics:
1. `core` tool failures may fail run per normal policy.
2. `compatibility` mapping failures must report whether failure occurred in:
   1. translation
   2. core tool execution
   3. post-processing/parity enforcement
3. `experimental` tool failures must not silently downgrade `core` invariants.
4. Required error code families:
   1. `capability_violation`
   2. `ring_policy_violation`
   3. `compat_mapping_missing`
   4. `compat_parity_violation`

Proof:
1. Conformance tests for all `core` tools.
2. Contract tests for all compatibility mappings.
3. Golden run parity tests for selected OpenClaw-equivalent scenarios.
4. Deterministic replay proof for `core` ring workloads.
5. Scoreboard metrics reproducible from ledger events only.

### Acceptance Gates (for promotion from compatibility -> core)

1. Stable schema for at least one defined release window.
2. Reliability threshold met (success and retry budgets from scoreboard policy).
3. Golden run parity set passes in live and replay modes.
4. No unresolved ring policy or capability violations for promoted tool.

## Non-Goals

1. Making all OpenClaw tools core tools.
2. Allowing compatibility pressure to weaken core determinism rules.
3. Treating experimental tools as production contracts.

