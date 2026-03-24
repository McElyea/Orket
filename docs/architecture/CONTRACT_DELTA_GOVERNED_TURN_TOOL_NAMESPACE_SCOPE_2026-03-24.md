# Contract Delta

## Summary
- Change title: Governed turn-tool namespace scope contract
- Owner: Orket Core
- Date: 2026-03-24
- Affected contract(s): `orket/runtime/tool_invocation_policy_contract.py`; `orket/application/workflows/tool_invocation_contracts.py`; governed turn-tool `RunRecord` and `StepRecord` publication

## Delta
- Current behavior: governed turn-tool execution already published run, step, effect, checkpoint, and final-truth authority, but namespace scope was implicit and tool-invocation contracts did not carry or enforce it.
- Proposed behavior: governed turn-tool execution now defaults to `issue:<issue_id>` namespace scope, fails closed on broader declared tool scopes, carries namespace scope in tool invocation manifests and execution context, and records namespace scope on governed turn-tool run and step authority.
- Why this break is required now: the accepted ControlPlane packet already locks a slim namespace contract and safe-tooling rules; leaving scope implicit on the one governed tool path with first-class control-plane authority would keep Workstream E in doc-only territory.

## Migration Plan
1. Compatibility window: additive for consumers that ignore extra manifest fields; fail-closed for governed turn-tool bindings that declare broader namespace scopes than the active run allows.
2. Migration steps:
   - add namespace error vocabulary and tool-invocation policy contract rule
   - propagate namespace scope through governed turn-tool manifests and execution context
   - persist namespace scope on governed turn-tool run and step records
3. Validation gates:
   - governed turn-tool dispatcher unit/integration proof
   - protocol receipt and run-ledger proof
   - control-plane integration proof for run, step, and checkpoint publication

## Rollback Plan
1. Rollback trigger: unexpected rejection of valid governed turn-tool executions due to namespace scope policy.
2. Rollback steps:
   - remove namespace scope enforcement from governed turn-tool policy checks
   - remove namespace fields from governed turn-tool manifest emission
   - keep persisted namespace fields as inert optional data if rollback stops at runtime behavior only
3. Data/state recovery notes: persisted namespace scope on run and step records is additive and can remain safely if runtime enforcement is rolled back.

## Versioning Decision
- Version bump type: additive contract extension with fail-closed runtime enforcement on governed turn-tool scope escalation
- Effective version/date: 2026-03-24
- Downstream impact: protocol ledger, receipt materialization, and run-summary consumers must tolerate the new manifest fields; governed turn-tool bindings may no longer declare out-of-scope namespaces silently
