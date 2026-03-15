# Orket Truthful Runtime Hardening Phase B Implementation Plan

Last updated: 2026-03-09
Status: Completed (archived closeout)
Owner: Orket Core
Canonical lane plan: `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
Depends on: Phase A completion

## Closeout Verification (2026-03-10)

1. Contract + integration suite (layers: unit/contract/integration):  
   `python -m pytest tests/runtime/test_tool_invocation_policy_contract.py tests/scripts/test_check_tool_invocation_policy_contract.py tests/runtime/test_route_decision_artifact.py tests/runtime/test_local_prompt_profiles.py tests/runtime/test_deterministic_mode_contract.py tests/runtime/test_model_profile_bios.py tests/runtime/test_local_remote_route_policy.py tests/runtime/test_operator_override_logging_policy.py tests/runtime/test_provider_quarantine_policy.py tests/runtime/test_provider_quarantine_policy_contract.py tests/application/test_turn_tool_dispatcher_support.py tests/application/test_turn_tool_dispatcher_policy_enforcement.py`
2. Governance contract check (layer: contract/integration):  
   `python scripts/governance/check_tool_invocation_policy_contract.py`
3. Live acceptance gate (layer: integration/live-truth governance):  
   `python scripts/governance/run_runtime_truth_acceptance_gate.py --workspace .`
4. Observed path: primary
5. Observed result: success (`ok=true`, `failures=[]`)

## 1. Objective

Make routing, prompting, and tool eligibility attributable and policy-bound so route and behavior decisions are explainable and controllable.

## 2. Scope Deliverables

1. Router decision artifact contract.
2. Prompt profile versioning contract and rendering rule versioning.
3. Tool invocation policy contract by run type.
4. Deterministic mode flag contract.
5. Model profile BIOS contract per provider-model pair.
6. Local-vs-remote route policy contract.
7. Human override lane contract.
8. Capability probation and regression quarantine policies.

## 3. Detailed Workstreams

### Workstream B1 - Routing Explainability
Tasks:
1. Define compact route decision artifact fields.
2. Emit route reason artifact per run in debug and policy-required lanes.
3. Ensure route decision fields link to capability truth and policy constraints.

Acceptance:
1. each route has a machine-readable explanation.
2. route rationale is attributable to declared capability/policy truth.

### Workstream B2 - Prompt and Tool Governance
Tasks:
1. Version prompt profiles and rendering rules.
2. Define tool eligibility matrix by run type and lane.
3. Enforce tool policy boundaries at runtime.

Acceptance:
1. prompt behavior changes are attributable by version.
2. policy-forbidden tool calls are blocked with explicit codes/events.

### Workstream B3 - Determinism and Control Lanes
Tasks:
1. Define deterministic mode behavior and disabled heuristics set.
2. Define override lane behavior for operator-forced routing/prompt strictness.
3. Implement probation/quarantine policy for unstable model-provider profiles.

Acceptance:
1. deterministic mode is reproducible and auditable.
2. unstable profiles can be downgraded/disabled by policy.

## 4. Verification Plan

1. Contract tests for route artifact shape, prompt profile version references, and tool policy matrix.
2. Integration tests for deterministic mode behavior and quarantine behavior.
3. End-to-end tests proving tool-denied and route-override semantics are user-visible and truthful.

## 5. Completion Gate

Phase B is complete when:
1. routing and prompting decisions are explicitly attributable,
2. tool usage cannot escape declared policy,
3. deterministic and override lanes are operational and test-backed.
