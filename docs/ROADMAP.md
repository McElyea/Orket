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

## Current Priority Order
1. `P3 Highest`: Architecture boundaries and maintenance checks stay green in CI and local proof loops.
2. `P4 Medium`: Additional acceptance telemetry and tooling polish outside stabilization goals.

## Completed: P0 Guard System Baseline
Summary (completed 2026-02-14):
1. Canonical guard contracts (`GuardContract`, `Violation`, `LoopControl`, `TerminalReason`) are enforced.
2. Runtime guard loop decisions are deterministic (`pass` / `retry` / `terminal_failure`).
3. Prompt/runtime rule ownership boundaries are enforced with conflict checks.
4. Hallucination guard V1 prompt overlays, scope checks, taxonomy, and persistent escalation are landed.

## Completed: P1 Security and Consistency Guard Rollout
Summary (completed 2026-02-14):
1. Security scope checks enforce path hardening.
2. Consistency scope checks enforce deterministic tool-call formatting.
3. Guard rule cataloging + ownership conflict checks are centralized.
4. Guard-domain telemetry and terminal-reason counters are reported in live acceptance patterns.

## Completed: P2 Prompt Engine Optimization Follow-Ups
Summary (completed 2026-02-14):
1. Offline candidate prompt generation workflow writes to candidate output only.
2. Stable vs candidate comparison uses eval and live-pattern deltas.
3. Promotion gates include guard-failure deltas and guard-domain regression counters.

## P3: Architecture Boundaries and Maintenance
Objective: keep dependency direction and volatility boundaries green while guard work lands.

Recurring Verification:
1. `python scripts/check_dependency_direction.py`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest tests/platform/test_architecture_volatility_boundaries.py -q`

## Completed Programs (Archived)
1. Prompt Engine foundation/versioning/runtime attribution/tooling (`P0-F1` to `P0-R1`) is complete.
2. Stabilizer policy hardening (`P-1` scaffolder/dependency manager/runtime verifier/deployment planner) is complete.
3. Canonical asset and acceptance gate hardening (`P2`) is complete.
4. V1 model behavior stabilization and `terminal_failure` session semantics are complete.

## Weekly Proof
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. `python -m scripts.report_live_acceptance_patterns`
