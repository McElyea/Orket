# Orket Phased Roadmap

Last updated: 2026-02-21
Owner: Orket Core
Status: Active execution backlog

## Purpose
This is the canonical working backlog for in-flight implementation work.

Use this file to:
1. Order remaining work by phase.
2. Re-prioritize without churning top-level docs.
3. Track forward-only execution until items are complete.

## Operating Rules
1. Keep only incomplete work in this file.
2. Remove completed items instead of archiving in-place.
3. Link deep details to plan files under `docs/implementation/`.
4. Update `Last updated` whenever phase priorities change.

## Phase 0: Active Now
1. Skill runtime adapter linkage.
Track: [Skills Implementation Plan](SkillsPlan.md)
Deliverables:
1. Wire Skill entrypoints to tool profile linkage in adapter/runtime path.
2. Add integration tests for declared-entrypoint-only invocation and permission guard enforcement.

## Phase 1: Next Up
1. No open Phase 1 items.

## Phase 2: Planned Later
1. No open Phase 2 items.

## Cross-Cutting Program Tracks
1. Deterministic memory and persistence program:
Archived under `docs/archive/MemoryPersistence/`.
2. Skills contract and loader program:
Tracked in `docs/implementation/SkillsPlan.md`.

## Guardrails (All Phases)
1. Pass/fail quality gates use Orket telemetry, not hardware sidecar metrics.
2. Invalid and polluted runs are excluded from KPI aggregates with no override.
3. `--include-invalid` may affect frontier/comparison views only.
4. Schema evolution is additive-only and backward compatible.
5. Every artifact includes `execution_lane` and `vram_profile`.

## Lane and Safety Baseline
1. `ci` lane: deterministic contract checks without hardware dependency.
2. `lab` lane: thermal/VRAM/throughput/variance validation on hardware.
3. `safe` profile: 50 percent cap.
4. `balanced` profile: 70 to 80 percent cap.
5. `stress` profile: 90 to 95 percent cap.
