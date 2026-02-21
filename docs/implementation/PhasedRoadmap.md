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
0. Roadmap kickoff (in progress): Memory contract freeze prep.
Track: [Memory Persistence Plan](MEMORY_PERSISTENCE_PLAN.md)
Execution slice:
1. Draft `docs/specs/MEMORY_CANONICALIZATION_JSON_V1.md`. Status: done (2026-02-21)
2. Draft `docs/specs/MEMORY_DETERMINISM_TRACE_SCHEMA.md`. Status: done (2026-02-21)
3. Draft `docs/specs/MEMORY_RETRIEVAL_TRACE_SCHEMA.md`. Status: done (2026-02-21)
4. Draft `docs/specs/MEMORY_TOOL_PROFILE_SCHEMA.md`. Status: done (2026-02-21)
5. Draft `docs/specs/MEMORY_BUFFER_STATE_MACHINE.md`. Status: done (2026-02-21)
6. Add `tests/contracts/test_memory_trace_contract.py`. Status: done (2026-02-21)
7. Add `tests/contracts/test_memory_retrieval_trace_contract.py`. Status: done (2026-02-21)
Done criteria:
1. All five docs created with required fields and version headers.
2. Includes canonical examples for text/plan/code_patch output-shape hashing.
3. Includes recovery single-owner lease semantics.
4. Contract tests exist and pass for determinism/retrieval/memory-buffer spec invariants.

Next execution slice:
1. Add `scripts/check_memory_determinism.py` skeleton for schema-level deterministic trace validation. Status: done (2026-02-21)
2. Wire script into a focused test (`tests/application/` or `tests/contracts/`) before workflow integration. Status: done (2026-02-21)

Next execution slice:
1. Implement `tests/application/test_buffered_write_isolation.py`. Status: done (2026-02-21)
2. Implement `tests/application/test_memory_commit_idempotency.py`. Status: done (2026-02-21)
3. Implement `tests/application/test_memory_commit_recovery.py`. Status: done (2026-02-21)

Next execution slice:
1. Wire `scripts/check_memory_determinism.py` into `.gitea/workflows/quality.yml`. Status: done (2026-02-21)
2. Add workflow gate coverage in `tests/platform/test_quality_workflow_gates.py`. Status: done (2026-02-21)

Next execution slice:
1. Resolve Phase 0 spec clarifications for canonicalization edge behavior. Status: done (2026-02-21)
2. Resolve retrieval deterministic-mode backend contract in retrieval trace spec. Status: done (2026-02-21)
3. Resolve buffer recovery lease defaults in buffer state-machine spec. Status: done (2026-02-21)
4. Resolve deterministic trace retention baseline in determinism trace spec. Status: done (2026-02-21)
5. Add contract tests for these clarified rules. Status: done (2026-02-21)

Next execution slice:
1. Add core memory contract models under `orket/core/contracts/memory_models.py`. Status: done (2026-02-21)
2. Add core validation tests for determinism and retrieval contracts. Status: done (2026-02-21)

1. Telemetry contract hardening across providers.
Success criteria:
1. Providers emit only canonical token/timing states.
2. Streaming and non-streaming transitions are consistent.
3. Adapter integration tests cover both paths.
4. All emitted artifacts include `execution_lane` and `vram_profile`.

2. Orchestration-overhead consistency guarantees.
Success criteria:
1. `internal_model_seconds` present on success and failure paths.
2. `orchestration_overhead_ratio` present on success and failure paths.
3. `run_quality_reasons` present on success and failure paths.

3. GPU sidecar parse policy finalization.
Success criteria:
1. Required fields parsed as canonical snake_case keys.
2. Optional fields parsed when present; missing optionals never fail execution.
3. `sidecar_parse_status` and `sidecar_parse_errors` emitted deterministically.

4. Valid-run policy enforcement end-to-end.
Success criteria:
1. Invalid runs excluded from KPI aggregates always.
2. Invalid runs excluded from recommendations by default.
3. `--include-invalid` affects frontier/comparison visibility only.

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
