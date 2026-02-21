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
1. Deterministic memory and persistence program: instrumentation implementation.
Track: [Memory Persistence Plan](MEMORY_PERSISTENCE_PLAN.md)
Deliverables:
1. Emit `memory.determinism_trace.v1` artifacts from runtime execution paths.
2. Emit `memory.retrieval_trace.v1` artifacts linked by `retrieval_event_id` and `event_id`.
3. Integrate `scripts/check_memory_determinism.py` into execution/reporting paths beyond workflow smoke.
4. Add integration tests covering deterministic trace emission and equivalence preconditions.

2. Telemetry contract hardening across providers.
Success criteria:
1. Providers emit only canonical token/timing states.
2. Streaming and non-streaming transitions are consistent.
3. Adapter integration tests cover both paths.
4. All emitted artifacts include `execution_lane` and `vram_profile`.

3. Orchestration-overhead consistency guarantees.
Success criteria:
1. `internal_model_seconds` present on success and failure paths.
2. `orchestration_overhead_ratio` present on success and failure paths.
3. `run_quality_reasons` present on success and failure paths.

4. GPU sidecar parse policy finalization.
Success criteria:
1. Required fields parsed as canonical snake_case keys.
2. Optional fields parsed when present; missing optionals never fail execution.
3. `sidecar_parse_status` and `sidecar_parse_errors` emitted deterministically.

5. Valid-run policy enforcement end-to-end.
Success criteria:
1. Invalid runs excluded from KPI aggregates always.
2. Invalid runs excluded from recommendations by default.
3. `--include-invalid` affects frontier/comparison visibility only.

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

## Phase 1: Next Up
1. Thermal gate and cooldown policy checks for GPU lab sessions.
Deliverables:
1. Add `wait_for_cooldown` policy checker for lab lane runs.
2. Emit deterministic polluted status reasons for cooldown timeout and hot-start conditions.
3. Add regression tests for pass/fail/skip thermal policy paths.

2. VRAM pre-flight guard rails as optional diagnostics.
Deliverables:
1. Add profile-driven thresholds per run (`safe`, `balanced`, `stress`).
2. Emit guard decision metadata into summary and check artifacts.
3. Add regression tests for threshold enforcement and skip handling.

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
