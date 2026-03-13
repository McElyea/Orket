# Runtime Stability Green Requirements

Last updated: 2026-03-13
Status: Archived
Owner: Orket Core
Source closeout lane: `docs/projects/archive/runtime-stability-closeout/IMPLEMENTATION-PLAN.md`

Archive note: Historical scope-discovery inputs preserved after the direct runtime-stability closeout lane completed on 2026-03-13.

## 1. Purpose

Define green requirements for removed runtime-stability topics that do not yet have enough coverage to support an honest closeout claim.

This project treats two conditions the same:
1. no meaningful shipped coverage,
2. slight or partial coverage that is still too weak or too ambiguous to close out truthfully.

## 2. Scope

In scope:
1. SPC-01 `core vs workloads boundary`
2. SPC-02 `golden run harness + deterministic replay + run determinism tests`
3. SPC-06 `core tool baseline + capability profiles per workload`

Out of scope:
1. SPC-03 prompt budgets and prompt diff tooling
2. SPC-04 tool reliability scoreboard
3. SPC-05 run compression/run graph/schema registry closeout implementation

## 3. Requirements

### 3.1 Boundary Closeout Requirements

1. Define the honest closeout target for the boundary item:
   1. current v0 boundary behavior only, or
   2. the full Focus Item 1 requirement set.
2. Resolve whether missing artifact requirements remain authoritative:
   1. `capability_profile.json`
   2. `workload_identity.json`
   3. `runtime_violation.json`
3. Define the exact proof set required for boundary closeout without relying on implied future controller-workload v1 work.

Acceptance:
1. The closeout target is explicit and non-ambiguous.
2. Source-of-truth docs no longer overclaim relative to current code.
3. Eventual implementation scope is bounded enough for a direct implementation plan.

### 3.2 Golden Harness Closeout Requirements

1. Decide the canonical replay/harness interface:
   1. protocol replay by run id, or
   2. fixture-based golden harness, or
   3. an explicitly versioned combination of both.
2. If fixture-based golden runs remain in scope, define:
   1. canonical fixture storage
   2. fixture schema
   3. live-mode and replay-mode behavior
   4. comparator modes and outputs
3. If protocol replay is the canonical replacement, define the required spec delta and proof expectations.

Acceptance:
1. The canonical operator surface is explicit.
2. Fixture expectations are either specified clearly or removed from active requirements.
3. Eventual implementation scope is bounded enough for a direct implementation plan.

### 3.3 Core Tool Baseline Closeout Requirements

1. Define the honest baseline breadth target for closeout:
   1. current minimal baseline, or
   2. broader OpenClaw-class support target.
2. Decide whether the richer per-tool contract fields remain required for closeout:
   1. `input_schema`
   2. `output_schema`
   3. `error_schema`
   4. `side_effect_class`
   5. timeout policy
   6. retry policy
3. Define how capability-profile enforcement relates to baseline-tool closeout:
   1. already sufficient as-is, or
   2. only one part of the unfinished baseline contract.

Acceptance:
1. Baseline breadth is explicit and testable.
2. Required registry metadata is explicit and testable.
3. Eventual implementation scope is bounded enough for a direct implementation plan.

## 4. Verification Requirements

1. Requirements output must identify exact source-of-truth documents to update on closeout.
2. Each scoped item must include the exact eventual proof layer needed:
   1. unit
   2. contract
   3. integration
   4. end-to-end
3. Docs hygiene must remain green.

## 5. Completion Criteria

1. Each in-scope item has an honest, bounded closeout target.
2. Each in-scope item has a named proof strategy and expected test layer.
3. The project outputs are sufficient to hand off each item to a direct implementation plan without reopening basic scope questions.

## 6. Implementation Pointer

Accepted implementation plan for this project:
1. `docs/projects/archive/runtime-stability-green-requirements/02-IMPLEMENTATION-PLAN.md`
