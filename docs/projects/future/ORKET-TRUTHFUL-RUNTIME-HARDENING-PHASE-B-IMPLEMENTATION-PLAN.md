# Orket Truthful Runtime Hardening Phase B Implementation Plan

Last updated: 2026-03-09
Status: Draft (queued)
Owner: Orket Core
Canonical lane plan: `docs/projects/future/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
Depends on: Phase A completion

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
