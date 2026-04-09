# Tool Execution Gate V1

Last updated: 2026-04-08
Status: Active (implemented first-slice authority)
Owner: Orket Core
Archived lane requirements: `docs/projects/archive/ExtensionCapabilityAuthorization/TGE04082026-LANE-CLOSEOUT/TOOL_GATE_ENFORCEMENT_REQUIREMENTS.md`
Implementation closeout authority: `docs/projects/archive/ExtensionCapabilityAuthorization/TGE04082026-LANE-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/ARCHITECTURE.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
4. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
5. `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`

## Authority posture

This document is the durable contract authority for the shipped Tool Gate Enforcement closure slice.

It freezes:
1. the one supported runtime tool-execution gate surface to close first
2. the authoritative internal gate composition for that surface
3. the supported, legacy, internal-only, and excluded path classifications
4. the closure proof and audit-artifact contract for this lane

The implemented slice is limited to:
1. construction-time gate authority requirements on the supported `run_card(...)` path
2. fail-closed governed dispatcher proof across the canonical `run_card(...)` path and normalized extension action path
3. fail-closed legacy `Agent.run(...)` blocking before any direct tool call when `tool_gate` authority is missing
4. the canonical `tool_gate_audit.v1` artifact and same-change event-taxonomy alignment for the governed turn-tool event family

## Purpose

Define one truthful supported runtime gate story so the first enforcement slice can close the canonical governed path without overstating coverage across legacy or extension capability surfaces.

## Decision lock

The following are fixed for this lane:
1. The supported runtime closure path is the canonical `run_card(...)` family collapsing into governed `TurnExecutor` execution.
2. The authoritative internal gate seam is `orket/application/workflows/turn_tool_dispatcher.py::ToolDispatcher.execute_tools(...)`.
3. Direct `ToolDispatcher` use is internal-only and is not a separate supported public runtime path.
4. The authoritative governed turn-tool gate is the composed dispatcher-level gate on that path, not the looser phrase "`ToolGate` or a stricter first-class policy gate."
5. `orket/agents/agent.py::Agent.run(...)` direct tool execution remains legacy compatibility debt, and the retained compatibility surface now fail-closes before any direct tool call when `tool_gate` authority is missing.
6. Direct `orket/tools.py::ToolBox.execute(...)` and direct card-family method invocation are internal helper surfaces, not independent gate-authority surfaces.
7. Card-family methods remain tool implementations; gate authority happens before those methods are invoked.
8. In scope for this lane are extension actions that delegate into `run_card(...)`, including extension engine actions normalized by `orket/extensions/runtime.py::ExtensionEngineAdapter.execute_action(...)`.
9. Out of scope for this lane are SDK capability registry invocations such as `model.generate`, `memory.write`, `memory.query`, `speech.transcribe`, `tts.speak`, `audio.play`, `voice.turn_control`, and similar workload capability calls. Those belong to `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`.
10. For supported runtime paths, missing gate authority is a construction-time failure condition for lane closure.

## Canonical supported path

The canonical supported runtime tool-execution path is:
1. `orket/runtime/execution/execution_pipeline_card_dispatch.py::run_card(...)`
2. runtime composition that constructs `TurnExecutor` with a required `ToolGate`
3. `orket/application/workflows/turn_executor.py::TurnExecutor.execute_turn(...)`
4. `orket/application/workflows/turn_tool_dispatcher.py::ToolDispatcher.execute_tools(...)`

Compatibility wrappers such as `run_issue(...)`, `run_epic(...)`, and `run_rock(...)` only count for this lane when they truthfully collapse into `run_card(...)`.

## Authoritative gate composition

The authoritative governed turn-tool gate on the canonical supported path is composed of four runtime-owned parts:
1. Dispatcher binding gate inside `ToolDispatcher.execute_tools(...)` for undeclared-tool, skill-contract, missing-permission, and runtime-limit admission before execution.
2. Dispatcher policy gate via `orket/application/workflows/turn_tool_dispatcher_support.py::tool_policy_violation(...)` for namespace, ring, capability-profile, determinism, and tool-to-tool boundary admission.
3. Mechanical gate via `orket/core/policies/tool_gate.py::ToolGate.validate(...)` for path, state-transition, destructive-operation, and content or policy checks owned by `ToolGate`.
4. Approval gate inside `ToolDispatcher.execute_tools(...)` for bounded operator approval-required tool continuation on the governed turn-tool path.

Dispatcher-local compatibility translation checks that still block before execution remain part of the same internal dispatcher seam and do not create a second authority center.

## Dispatch-path classification

This lane uses the following classifications:
1. `primary`: canonical closure path for this lane
2. `legacy-compatibility`: inventoried path retained for compatibility but not part of the supported closure claim
3. `internal-only`: helper or implementation seam that is not a supported public runtime path by itself
4. `out-of-scope`: real runtime behavior intentionally excluded from this lane and tracked elsewhere

The current frozen path matrix is:
1. `run_card.turn_executor.tool_dispatcher`
   - classification: `primary`
   - notes: one canonical public runtime dispatcher over normalized card facts
2. direct `TurnExecutor.execute_turn(...)`
   - classification: `internal-only`
   - notes: authoritative construction and delegation seam, but not an independent public runtime story
3. direct `ToolDispatcher.execute_tools(...)`
   - classification: `internal-only`
   - notes: authoritative internal gate seam, not a separate supported public path
4. `Agent.run` direct tool execution
   - classification: `legacy-compatibility`
   - notes: retained inventory surface that now fail-closes before any direct tool call when `tool_gate` authority is missing
5. direct `ToolBox.execute(...)`
   - classification: `internal-only`
   - notes: supported only as an execution helper when reached from the dispatcher path
6. direct card-family method invocation
   - classification: `internal-only`
   - notes: tool implementation detail, not gate authority
7. extension engine action normalized to `run_card(...)`
   - classification: `primary`
   - notes: in scope only because it re-enters the canonical runtime dispatcher
8. SDK capability registry invocation inside extension workloads
   - classification: `out-of-scope`
   - notes: separate authorization model tracked in the shipped first-slice authority at `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`

## Fail-closed closure contract

For this lane, closure requires:
1. Every `primary` path constructs with gate authority available before execution can begin.
2. Missing gate authority on a `primary` path is a construction-time failure for lane closure, not degraded success.
3. Retained legacy-compatibility or internal-only seams do not count as supported closure proof.
4. If a retained legacy-compatibility path can still reach tool execution outside the canonical dispatcher gate, lane closure is blocked until that path either:
   1. routes into the canonical dispatcher contract, or
   2. returns a machine-readable blocked result before any tool call

## Allowed-root contract for this lane

The path-containment rule for this lane is fixed as follows:
1. `write_file` may write only under `workspace_root`.
2. reference roots are read-only for generic tool-write purposes.
3. extension `artifact_root` belongs to the extension artifact contract and is not generic `write_file` authority for this lane.
4. `durable_root` is host-owned persistence and is not generic tool-write territory unless a future specific tool contract explicitly says otherwise.

The containment proof for this lane is therefore: blocked generic tool writes produce no effect outside `workspace_root`.

## Telemetry closure contract

For the canonical governed turn-tool path, the required event family for lane closure is:
1. `tool_call_blocked`
2. `tool_approval_required`
3. `tool_approval_granted`
4. `tool_call_result`
5. `tool_call_exception`
6. `determinism_violation`
7. `tool_timeout`

For this lane, a gate rejection means `side_effect_observed=false`.

Current-state note:
1. `docs/architecture/event_taxonomy.md` remains the active current-state event-field authority.
2. This contract freezes the event family and rejection semantics for the implemented closure slice.
3. Same-change event-taxonomy alignment is required whenever this emitted-event authority changes again.

Legacy `tool_blocked` from direct `Agent.run(...)` remains compatibility telemetry and is not part of the canonical governed-turn tool event family.

## Audit artifact contract

Lane closure requires one durable JSON audit artifact that records the frozen path matrix and deny-all proof result.

Canonical operator path:
1. `python scripts/security/build_tool_gate_audit.py --strict`

Stable output path:
1. `benchmarks/results/security/tool_gate_audit.json`

Minimum schema:

```json
{
  "schema_version": "tool_gate_audit.v1",
  "gate_surface": "governed_turn_tool_gate_v1",
  "paths": [
    {
      "dispatch_path": "run_card.turn_executor.tool_dispatcher",
      "entrypoint": "orket/application/workflows/turn_executor.py::TurnExecutor.execute_turn",
      "supported": true,
      "path_status": "primary",
      "gate_type": "composed",
      "deny_all_expected_result": "blocked",
      "observed_result": "blocked",
      "proof_ref": "python -m pytest -q ...",
      "legacy_status": "",
      "non_runtime_reason": "",
      "out_of_scope_lane": "",
      "side_effect_observed": false,
      "notes": ""
    }
  ]
}
```

Required path fields are:
1. `dispatch_path`
2. `entrypoint`
3. `supported`
4. `path_status`
5. `gate_type`
6. `deny_all_expected_result`
7. `observed_result`
8. `proof_ref`
9. `legacy_status`
10. `non_runtime_reason`
11. `out_of_scope_lane`
12. `side_effect_observed`
13. `notes`

## Proof contract

Closure proof for this lane requires:
1. contract proof for the composed deny policy rules on the canonical dispatcher path
2. integration proof that deny-all blocks tool execution across all `primary` paths in the audit artifact
3. integration proof that blocked generic write attempts create or modify no file outside `workspace_root`
4. audit-artifact publication using the schema above

The lane does not close by claiming SDK capability authorization proof under extension workloads.
