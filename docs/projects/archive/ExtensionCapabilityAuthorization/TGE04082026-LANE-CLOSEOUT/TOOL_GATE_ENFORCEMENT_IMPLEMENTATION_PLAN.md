# Tool Gate Enforcement Implementation Plan

Last updated: 2026-04-08
Status: Completed
Owner: Orket Core

Authorities:
1. `docs/specs/TOOL_EXECUTION_GATE_V1.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/architecture/event_taxonomy.md`

## Goal

Close one truthful runtime tool-execution gate slice without overstating broader runtime coverage.

The completed slice is:
1. canonical `run_card(...) -> TurnExecutor -> ToolDispatcher`
2. extension engine actions that normalize into that same `run_card(...)` path
3. retained legacy `Agent.run(...)` fail-closed blocking before any direct tool call when `tool_gate` authority is missing

## Completed work

1. Added construction-time fail-closed checks on `TurnExecutor` and `ToolDispatcher` when `tool_gate` authority is missing.
2. Made legacy `Agent.run(...)` direct tool execution return a machine-readable blocked result before any tool call when `tool_gate` authority is absent.
3. Added canonical integration proof for:
   1. deny-all blocking on the supported `run_card(...)` path
   2. deny-all blocking on normalized extension actions that re-enter `run_card(...)`
   3. blocked `write_file` workspace escapes producing no file outside `workspace_root`
4. Published the canonical audit artifact command and stable output path at `python scripts/security/build_tool_gate_audit.py --strict` and `benchmarks/results/security/tool_gate_audit.json`.
5. Promoted `docs/specs/TOOL_EXECUTION_GATE_V1.md` from planning authority to implemented first-slice authority and synchronized `CURRENT_AUTHORITY.md` plus `docs/architecture/event_taxonomy.md`.

## Verification plan executed

1. `python -m pytest -q tests/application/test_agent_model_family_registry.py tests/application/test_tool_gate_enforcement_closure.py tests/scripts/test_build_tool_gate_audit.py`
2. `python -m pytest -q tests/application/test_turn_tool_dispatcher_policy_enforcement.py tests/runtime/test_extension_components.py tests/core/test_runtime_event_logging.py`
3. `python scripts/security/build_tool_gate_audit.py --strict`
4. `python scripts/governance/check_docs_project_hygiene.py`

## Closeout rule

This lane closes only if:
1. both `primary` rows in `tool_gate_audit.v1` are `blocked` with `side_effect_observed=false`
2. legacy `Agent.run(...)` direct tool execution is blocked before any tool call when `tool_gate` authority is missing
3. same-change doc and roadmap sync passes docs hygiene
