# Orket Roadmap (Active Only)

Last updated: 2026-02-14.

## North Star
Ship one canonical, reliable pipeline that passes this exact flow with deterministic guard governance:
1. `requirements_analyst`
2. `architect`
3. `coder`
4. `code_reviewer`
5. `integrity_guard`

If this flow is not mechanically proven with canonical assets and machine-readable guard contracts, we are not done.

## Operating Rules
1. Keep changes small and reversible.
2. No architecture pivots while stabilization work is active.
3. Every change must map to a failing or missing test.
4. Single owner per rule:
   - `Role + Skill + Dialect` define behavior, style, structure, and intent.
   - `Guards` enforce runtime correctness constraints.
   - `Guard Agent` validates only and never generates content.
5. Guard outcomes must be deterministic, machine-readable, and diagnosable from runtime artifacts.

## Priority Order (Highest First)
1. `P3`: Architecture boundary enforcement and maintenance checks.
2. `P4`: Operational hardening of CI cadence and proof loops.

## Active Work: P3 Architecture Boundaries and Maintenance
Objective: keep dependency direction and volatility boundaries green while stabilized guard/prompt systems continue to evolve.

Recurring Verification:
1. `python scripts/check_dependency_direction.py`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest tests/platform/test_architecture_volatility_boundaries.py -q`

## Active Work: P4 Operational Hardening
Objective: maintain deterministic weekly proof loops and avoid silent policy drift.

1. Keep `quality.yml` gate duplication checks green in both architecture and quality jobs.
2. Keep prompt promotion thresholds file and candidate comparison tests in lockstep.
3. Keep live acceptance report schema counters stable (`runtime_event_envelope_count`, `runtime_event_schema_v1_count`).
4. Keep model compliance summaries present in pattern reports.

## Recently Completed
1. `P0-R1` Guard rule registry landed with owner/severity/scope and duplicate/unknown rule enforcement.
2. `P0-R2` Canonical verification scope builder landed and all guard diagnostics route through normalized scope.
3. `P0-R3` Retry fingerprint cutoff landed with deterministic `MODEL_NON_COMPLIANT` terminal escalation.
4. `P0-R4` Guard evaluator/controller split landed with isolated policy logic.
5. `P0-R5` Hallucination context partitioning landed (`active/passive/archived`).
6. `P1-R1` Prompt linter landed with canonical violation schema and strict/soft outputs.
7. `P1-R2` Promotion criteria enforcement landed in candidate comparison + CLI promotion gating.
8. `P2-R1` Structured runtime event envelope landed with durable JSONL runtime event artifacts.
9. `P2-R2` Model compliance scoring landed in live acceptance pattern reporting.

## Weekly Proof
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. `python -m scripts.report_live_acceptance_patterns`
