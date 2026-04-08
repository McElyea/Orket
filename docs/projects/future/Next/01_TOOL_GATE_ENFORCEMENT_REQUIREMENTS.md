# Tool Gate Enforcement Requirements

Last updated: 2026-04-07
Status: Future requirements draft
Owner: Orket Core

Related authority:
1. `docs/ARCHITECTURE.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
4. `orket/core/policies/tool_gate.py`
5. `orket/application/workflows/turn_tool_dispatcher.py`

## Posture

This is a future requirements draft, not active roadmap execution authority.

The first implementation slice should close the gap between "a gate exists" and "all runtime tool execution is actually gated." This must be treated as a security-boundary requirement before broader external extension work.

## Problem

Orket has a `ToolGate` policy surface and governed turn-tool enforcement, but the system should not rely on path familiarity or caller discipline to prevent bypasses. Any runtime path that can execute a tool must either pass through one canonical gate decision or fail closed before execution.

## Goals

1. Build an inventory of all runtime-reachable tool dispatch paths.
2. Prove that every runtime-reachable tool execution path invokes `ToolGate` or a stricter first-class policy gate before side effects.
3. Add a first real deny policy that blocks at least undeclared tools, path escapes outside the workspace, and unsupported namespace or capability declarations.
4. Add integration proof that a deny-all gate prevents tool execution across the audited supported dispatch paths.
5. Preserve test-only fakes without letting them imply runtime safety.

## Non-Goals

1. Do not design a broad policy language.
2. Do not create a marketplace or extension registry.
3. Do not claim OS-level sandboxing from `ToolGate`.
4. Do not move runtime authority into extension code or UI code.
5. Do not weaken existing governed turn-tool control-plane publication.

## Requirements

1. The implementation must produce a reviewed inventory of tool execution entrypoints, including legacy `Agent` execution, `TurnExecutor`, `ToolDispatcher`, card-family tools, and extension workload execution where tool effects can occur.
2. Runtime tool execution must fail closed if no gate is available, unless the path is explicitly documented as non-runtime, test-only, or unreachable from production orchestration.
3. A deny-all gate test must prove that zero tool calls execute through each supported runtime dispatch entrypoint under the same policy.
4. A path-containment test must attempt a workspace escape and prove the attempted effect does not happen.
5. A namespace and capability policy test must prove unsupported declarations are rejected before side effects.
6. Existing `tool_gate=None` compatibility seams must either be removed from runtime construction or converted into explicit degraded or blocked behavior.
7. Gate rejection telemetry must identify the tool name, rejection reason, dispatch path, and whether any side effect was observed.
8. Gate success telemetry must not claim execution success until the underlying tool result has been observed.
9. Extension validation success must remain admissibility evidence only; it must not bypass runtime tool authorization.
10. Any changed authority wording must be updated in `CURRENT_AUTHORITY.md` and related specs in the same change.

## Acceptance Proof

Required proof:
1. Contract tests for the first real policy rules.
2. Integration tests for deny-all behavior across audited runtime dispatch paths.
3. Integration proof that path escape attempts leave no created or modified file outside the allowed root.
4. A short audit artifact or test fixture that lists audited paths and their gate result.

Proof classification:
1. Gate policy rules: contract proof.
2. Runtime dispatch coverage: integration proof.
3. Real file non-effect on blocked writes: integration proof.

Completion must report observed path as `primary`, `fallback`, `degraded`, or `blocked`, and observed result as `success`, `failure`, `partial success`, or `environment blocker`.
