# MR-3 Requirements: Boundary Hardening and Contract Governance

Date: 2026-02-24  
Type: enforcement hardening (may include controlled contract breaks)

## Objective

Make architecture boundaries enforceable, measurable, and resistant to drift so modular refactors remain stable over time.

## In Scope

1. Unified dependency-direction policy across docs/tests/scripts.
2. Removal of `root` blind spot in dependency checks.
3. Explicit module/layer map with allowed edges.
4. CI gates for new forbidden edges and volatility hotspots.
5. Contract governance process for any intentional boundary break.

## Out of Scope

1. Unplanned large rewrites without migration paths.
2. Silent boundary exceptions.

## Functional Requirements

1. Every top-level `orket/*` package must map to a declared layer/module.
2. Dependency checker must reject undefined/unmapped layer edges.
3. Policy conflicts (docs vs tests vs scripts) must fail a guard test.
4. CI must emit machine-readable boundary-drift report artifacts.

## Governance Requirements

1. Any contract break requires:
- documented delta
- migration note
- rollback strategy
- version bump decision

2. `application -> adapters` policy must be explicitly resolved:
- either allowed by design with rationale and guard constraints
- or disallowed with phased migration plan to ports

## Quality Requirements

1. Guard scripts and tests must not pass on empty scan sets.
2. Boundary drift detection must be deterministic.
3. Quality workflow must execute boundary checks in quick and full lanes.

## Acceptance Criteria

1. No unknown layers in dependency graph.
2. Boundary policy represented identically in architecture docs and enforcement code.
3. CI rejects deliberate forbidden import probes.
4. Drift reports are generated and archived per run.

