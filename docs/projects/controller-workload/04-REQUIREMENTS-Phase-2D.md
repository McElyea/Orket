# Controller Workload Phase 2D Requirements (Reliability Hardening + v1 Planning)

Last updated: 2026-03-08
Status: Accepted
Owner: Orket Core
Initiative authority: `docs/projects/controller-workload/02-INITIATIVE-MINI-ROADMAP.md`
Runtime contract authority: `docs/specs/CONTROLLER_WORKLOAD_V1.md`
Observability contract authority: `docs/specs/CONTROLLER_OBSERVABILITY_V1.md`

## 1. Purpose

Define the final Phase 2 slice for initiative steps 21-22:
1. reliability hardening cycle (flake boundaries, retry boundaries, failure taxonomy)
2. v1 planning handoff for bounded parallelism and broader child-type support

## 2. Scope

In scope:
1. reliability hardening findings + fixes for controller runtime/test paths
2. deterministic flake-boundary and failure-taxonomy evidence capture
3. v1 planning handoff packet with explicit non-goals and migration boundaries

Out of scope:
1. implementation of bounded parallel execution itself
2. support for non-`sdk_v0` child contract styles in runtime

## 3. Requirements

### 3.1 Reliability Hardening
1. identify and remediate high-probability controller reliability drifts
2. define/record retry boundaries explicitly (what retries, what never retries)
3. publish failure taxonomy for controller run and child execution failures

Acceptance:
1. targeted hardening tests pass
2. reliability evidence includes exact failing step/error where failures remain

### 3.2 v1 Planning Handoff
1. produce planning packet for bounded parallel child execution option
2. include compatibility implications for current contracts/specs/tests
3. document migration constraints and rollback boundaries

Acceptance:
1. planning packet is actionable and linked from active roadmap lane

## 4. Verification Requirements

1. unit/integration tests for any reliability hardening changes
2. evidence artifacts for observed reliability paths
3. docs hygiene/governance checks remain green

## 5. Completion Criteria

1. reliability hardening cycle outcomes are documented and verified
2. v1 planning handoff packet is published and linked
3. Phase 2 lane is ready for full initiative closeout

## 6. Implementation Pointer

Accepted implementation plan for this slice:
1. `docs/projects/controller-workload/05-IMPLEMENTATION-PLAN-Phase-2D.md`
