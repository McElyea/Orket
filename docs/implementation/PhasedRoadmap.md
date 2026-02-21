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
1. No open Phase 0 items.

Next execution slice:
1. Emit memory determinism trace artifacts from runtime execution path. Status: done (2026-02-21)
2. Emit memory retrieval trace artifact envelope from runtime execution path. Status: done (2026-02-21)
3. Add runtime emission coverage test (`tests/application/test_memory_trace_emission.py`). Status: done (2026-02-21)

Next execution slice:
1. Add deterministic equivalence comparator script for left/right traces. Status: done (2026-02-21)
2. Add pass/fail script tests for deterministic equivalence comparison. Status: done (2026-02-21)

Next execution slice:
1. Wire `scripts/compare_memory_determinism.py` into `.gitea/workflows/quality.yml`. Status: done (2026-02-21)
2. Add workflow gate coverage for comparator in `tests/platform/test_quality_workflow_gates.py`. Status: done (2026-02-21)

Next execution slice:
1. Add trace truncation marker metadata to runtime memory trace artifacts. Status: done (2026-02-21)
2. Enforce max trace size + truncation marker in `scripts/check_memory_determinism.py`. Status: done (2026-02-21)
3. Add truncation enforcement tests in `tests/application/test_check_memory_determinism_script.py`. Status: done (2026-02-21)

Next execution slice:
1. Expand runtime memory trace events from single turn event to lifecycle events (`before_prompt`, `after_model`, `before_tool`, `after_tool`). Status: done (2026-02-21)
2. Update emission coverage tests for lifecycle event presence. Status: done (2026-02-21)

Next execution slice:
1. Add persistence-backed commit integration store for memory commit semantics tests. Status: done (2026-02-21)
2. Add restart/idempotency persistence integration tests for commit state. Status: done (2026-02-21)

Next execution slice:
1. Add orchestration-overhead consistency checker for benchmark report telemetry. Status: done (2026-02-21)
2. Wire consistency checker into `.gitea/workflows/quality.yml` and gate test coverage. Status: done (2026-02-21)

Next execution slice:
1. Normalize benchmark telemetry artifacts to always include `execution_lane` and `vram_profile`. Status: done (2026-02-21)
2. Add telemetry artifact contract checker for canonical token/timing status and lane/profile keys. Status: done (2026-02-21)
3. Wire telemetry artifact checker into `.gitea/workflows/quality.yml` and gate test coverage. Status: done (2026-02-21)

Next execution slice:
1. Add sidecar parse policy contract checker for quant sweep summaries. Status: done (2026-02-21)
2. Add valid-run frontier policy checker for quant sweep summaries. Status: done (2026-02-21)
3. Wire both policy checkers into `.gitea/workflows/quant-sweep-full-selfhosted.yml` with workflow gate coverage tests. Status: done (2026-02-21)

## Phase 1: Next Up
1. No open Phase 1 items.

Next execution slice:
1. Confirm thermal cooldown policy enforcement via `scripts/check_lab_guards.py` with deterministic reason codes and pass/fail/skip regression tests. Status: done (2026-02-21)
2. Confirm VRAM pre-flight profile thresholds (`safe`, `balanced`, `stress`) and guard metadata emission via quant sweep + guard artifacts. Status: done (2026-02-21)
3. Enforce lab guard execution in `.gitea/workflows/quant-sweep-full-selfhosted.yml` with workflow gate coverage tests. Status: done (2026-02-21)

## Phase 2: Planned Later
1. Add sidecar schema specs under `docs/specs/` for long-term contract governance.
2. Add VRAM fragmentation analyzer experiments.
3. Add model selector and adaptive routing prototypes after diagnostics evidence is stable.

## Cross-Cutting Program Tracks
1. Deterministic memory and persistence program:
[Memory Persistence Plan](MEMORY_PERSISTENCE_PLAN.md)

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
