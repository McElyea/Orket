# Tool Gate Enforcement Requirements

Last updated: 2026-04-08
Status: Archived requirements
Owner: Orket Core
Implementation closeout authority: `docs/projects/archive/ExtensionCapabilityAuthorization/TGE04082026-LANE-CLOSEOUT/CLOSEOUT.md`

Related authority:
1. `docs/ARCHITECTURE.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/TOOL_EXECUTION_GATE_V1.md`
4. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
5. `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`
6. `orket/core/policies/tool_gate.py`
7. `orket/application/workflows/turn_tool_dispatcher.py`

## Posture

This is the archived requirements record for the completed Tool Gate Enforcement first slice.

The durable implemented authority for this lane now lives in `docs/specs/TOOL_EXECUTION_GATE_V1.md`.

This file remains historical source material for the completed slice; it is not active roadmap execution authority.

## Problem

Orket has a `ToolGate` policy surface and governed turn-tool enforcement, but the system should not rely on path familiarity or caller discipline to prevent bypasses.

The requirements risk was previously overstating coverage by treating multiple unlike execution paths as if they were co-equal. This lane now freezes one canonical governed path first and explicitly classifies legacy, internal-only, and out-of-scope paths instead of smoothing them together.

## Frozen closure decisions

The lane is now locked to the following decisions:
1. Supported runtime closure path: canonical `run_card(...)` family collapsing into `TurnExecutor`.
2. Authoritative internal gate seam: `ToolDispatcher.execute_tools(...)`.
3. Canonical governed turn-tool gate composition:
   1. dispatcher binding gate
   2. dispatcher policy gate
   3. `ToolGate.validate(...)` mechanical gate
   4. approval gating inside `turn_tool_dispatcher.py`
4. `Agent.run(...)` direct tool execution stays in inventory but is legacy compatibility or noncanonical debt, not a supported closure path.
5. Direct `ToolBox.execute(...)` and direct card-family method invocation are internal-only helper or implementation seams, not independent runtime gate surfaces.
6. Extension actions that normalize into `run_card(...)` are in scope for this lane.
7. SDK capability registry invocations are out of scope for this lane and move to `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`.

## Goals

1. Audit runtime-reachable tool-dispatch paths against the frozen path classifications in `docs/specs/TOOL_EXECUTION_GATE_V1.md`.
2. Close the canonical governed `run_card(...) -> TurnExecutor -> ToolDispatcher` gate surface first.
3. Add a first deny policy on that path that blocks at least undeclared tools, path escapes outside `workspace_root`, and unsupported namespace or capability declarations.
4. Add deny-all proof across every path classified `primary` in the audit artifact.
5. Preserve truthful inventory for legacy and internal-only seams without letting them imply runtime safety.

## Non-Goals

1. Do not design a broad policy language.
2. Do not create a marketplace or extension registry.
3. Do not claim OS-level sandboxing from `ToolGate`.
4. Do not move runtime authority into extension code or UI code.
5. Do not weaken existing governed turn-tool control-plane publication.
6. Do not close this lane by claiming SDK capability authorization proof under extension workloads.

## Requirements

1. The implementation must produce the durable audit artifact defined by `docs/specs/TOOL_EXECUTION_GATE_V1.md`, including the frozen dispatch-path classifications and deny-all proof result for each audited path.
2. `primary` runtime paths must fail closed on missing gate authority at construction time.
3. Legacy-compatibility and internal-only paths must remain inventoried truthfully, but they do not count as supported closure proof.
4. A deny-all gate test must prove that zero tool calls execute through each path classified `primary` under the same policy.
5. A path-containment test must attempt a `write_file` workspace escape and prove the attempted effect does not happen outside `workspace_root`.
6. A namespace and capability policy test must prove unsupported declarations are rejected before side effects on the canonical dispatcher path.
7. Extension validation success must remain admissibility evidence only; it must not bypass runtime tool authorization.
8. SDK capability registry invocation proof must remain outside this lane's closure claim.
9. Any changed authority wording must be updated in `CURRENT_AUTHORITY.md` and related specs in the same change.

## Acceptance proof

Required proof:
1. Contract tests for the composed deny policy on the canonical dispatcher path.
2. Integration tests for deny-all behavior across audited `primary` paths.
3. Integration proof that blocked generic write attempts create or modify no file outside `workspace_root`.
4. Publication of the audit artifact required by `docs/specs/TOOL_EXECUTION_GATE_V1.md`.

Proof classification:
1. Gate policy rules: contract proof.
2. Runtime dispatch coverage: integration proof.
3. Real file non-effect on blocked writes: integration proof.

Completion must report observed path as `primary`, `fallback`, `degraded`, or `blocked`, and observed result as `success`, `failure`, `partial success`, or `environment blocker`.
