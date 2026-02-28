# Orket Extension SDK v0

This folder is the active project spec for the Orket Extension SDK v0 surface.

## Purpose

Define one clear public extension seam for deterministic workloads with explicit capability injection.

Planning mode:
- Gameplay implementation may pause temporarily.
- SDK seam and migration decisions continue from this folder as source of truth.
- Term lock: use `deterministic runtime policy` to refer to hint + disambiguation behavior.

Public seam lock:
- `Workload.run(ctx, input) -> WorkloadResult`

Non-promise:
- Engine-internal turn orchestration types, including `TurnResult`, are private and may change without public compatibility guarantees.

## Documents

- `00-IMPLEMENTATION-PLAN-SDK-LAYER-0.md`: Layer-0 lock, gameplay-kernel alignment constraints, and stop/resume checkpoint.
- `01-REQUIREMENTS.md`: Product and contract requirements for SDK v0.
- `02-IMPLEMENTATION-PLAN.md`: Execution phases, tasks, ownership slices, and test strategy.
- `03-MIGRATION-AND-COMPAT.md`: Migration policy, compatibility guarantees, and deprecation criteria.

## Scope Summary

- v0 includes minimal SDK modules: `manifest`, `capabilities`, `workload`, `result`, `testing`.
- v0 demo extension target is external: `orket-extension-mystery-game-demo`.
- Legacy extension path remains temporarily supported during migration via dual-path runtime bridging.
- Near-term execution adds:
  - `Phase 0` lock-and-extract sequencing
  - deterministic runtime policy hardening (`Phase 5`) for hint/disambiguation loop quality without expanding SDK public API.
