# Contract Delta Proposal

## Summary
- Change title: Tool Execution Gate first-slice closeout
- Owner: Orket Core
- Date: 2026-04-08
- Affected contract(s): `docs/specs/TOOL_EXECUTION_GATE_V1.md`, `CURRENT_AUTHORITY.md`, `docs/architecture/event_taxonomy.md`

## Delta
- Current behavior: `docs/specs/TOOL_EXECUTION_GATE_V1.md` was planning authority for a future enforcement lane, while `Agent.run(...)` could still execute direct tool calls without `tool_gate` authority and no canonical audit artifact existed.
- Proposed behavior: the canonical `run_card(...)` tool-execution path is now implemented first-slice authority with construction-time gate requirements, retained legacy `Agent.run(...)` now fails closed before any direct tool call when `tool_gate` is missing, and the stable audit artifact is `benchmarks/results/security/tool_gate_audit.json`.
- Why this break is required now: the lane could not truthfully close while the legacy bypass remained executable and while the governed path lacked a durable audit artifact.

## Migration Plan
1. Compatibility window: none for unsupported direct-agent execution without `tool_gate` authority; the legacy surface now blocks immediately.
2. Migration steps: route supported runtime tool execution through the canonical governed dispatcher path, or inject a `tool_gate` when a retained legacy compatibility surface must stay callable.
3. Validation gates: `tests/application/test_tool_gate_enforcement_closure.py`, `tests/application/test_agent_model_family_registry.py`, `tests/scripts/test_build_tool_gate_audit.py`, and `python scripts/security/build_tool_gate_audit.py --strict`.

## Rollback Plan
1. Rollback trigger: canonical deny-all proof or workspace-containment proof regressions.
2. Rollback steps: restore the previous planning-authority posture in `docs/specs/TOOL_EXECUTION_GATE_V1.md`, remove the enforced legacy blocking only with an explicit replacement gate story, and regenerate the audit artifact after the replacement behavior is verified.
3. Data/state recovery notes: the audit artifact is rerunnable and diff-ledger backed; no state migration is required.

## Versioning Decision
- Version bump type: documentation and governance contract promotion only
- Effective version/date: 2026-04-08
- Downstream impact: retained legacy callers that rely on direct `Agent.run(...)` tool execution without `tool_gate` authority now receive a blocked result instead of executing tools
