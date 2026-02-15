# Orket Roadmap

Last updated: 2026-02-15.

## Operating Constraints (Current)
1. Orket engine loop remains the runtime; storage backend is pluggable.
2. Monolith remains default; microservices stay policy-controlled.
3. Frontend policy is Vue-only when a frontend is required.
4. iDesign is backburnered and not an active gate.
5. Small-task minimum team is one builder (`coder` or `architect`) plus one mandatory `code_reviewer`.
6. Replan limit is terminal: `replan_count > 3` halts with rejection semantics.

## Priority 1: Determinism Maintenance (Recurring)
Objective: keep quality and policy gates green while architecture/state work continues.

1. Keep these commands green:
   - `python -m pytest tests -q`
   - `python scripts/check_dependency_direction.py`
   - `python scripts/check_volatility_boundaries.py`
   - `python scripts/run_gitea_state_rollout_gates.py --out benchmarks/results/gitea_state_rollout_gates.json --require-ready`
2. Keep readiness artifacts fresh:
   - `python scripts/run_monolith_variant_matrix.py --execute --out benchmarks/results/monolith_variant_matrix.json`
   - `python -m scripts.report_live_acceptance_patterns --matrix benchmarks/results/monolith_variant_matrix.json`
   - `python scripts/check_monolith_readiness_gate.py --matrix benchmarks/results/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only`

## Priority 2: Architecture Pilot Monitoring (Recurring)
Objective: continue side-by-side monolith vs microservices evidence while runtime/storage work advances.

1. Refresh pilot matrix:
   - `python scripts/run_architecture_pilot_matrix.py --execute --out benchmarks/results/architecture_pilot_matrix.json --rotate-prev-out benchmarks/results/architecture_pilot_matrix_prev.json`
2. Re-evaluate stability:
   - `python scripts/check_microservices_pilot_stability.py --artifacts benchmarks/results/architecture_pilot_matrix_prev.json benchmarks/results/architecture_pilot_matrix.json --required-consecutive 2 --out benchmarks/results/microservices_pilot_stability_check.json`
3. Keep runtime policy output aligned:
   - `microservices_unlocked`
   - `microservices_pilot_stable`

## Backburner (Not Active)
1. Additional frontend frameworks beyond Vue.
2. iDesign-first enforcement.
3. Architecture expansion beyond controlled microservices policy/pilot monitoring.

## Priority 3: Benchmark Program (Phased)
Objective: convert the benchmark ideas into an executable, repeatable program with explicit acceptance gates.

### Phase 4: Tier 1-3 Rollout (Core Reliability)
Scope:
1. Operationalize tasks `001`-`060` with executable instructions.
2. Add failure-injection scenarios for crash-sensitive tier-3 tasks.
3. Document expected deterministic behavior and allowed exceptions.

Acceptance criteria:
1. One command executes tasks `001`-`060` and produces a report artifact.
2. At least 5 fault-injection cases are implemented for tier-3 (timeout, partial write, malformed input, interrupted run, retry path).
3. Tier-1 deterministic tasks show zero hash drift across configured reruns.

### Phase 5: Tier 4-6 Rollout (Architecture and Stress)
Scope:
1. Operationalize tasks `061`-`100` with explicit acceptance contracts.
2. Add spec-clarification checkpoints for ambiguous tier-4 tasks.
3. Add multi-step convergence checks for tier-6 stress tasks.

Acceptance criteria:
1. Tasks `061`-`100` are runnable through the same benchmark entrypoint.
2. Tier-6 tasks emit convergence metrics (`attempts_to_pass`, `drift_rate`).
3. Reviewer and architecture compliance checks are represented in run artifacts.

### Phase 6: Automation, Reporting, and Leaderboard
Scope:
1. Add scheduled benchmark execution in CI.
2. Build a report visualizer for trend analysis.
3. Publish a leaderboard by model mix and venue.

Acceptance criteria:
1. A nightly GitHub Actions workflow runs benchmark suites and stores artifacts.
2. Trend reports show determinism, score, latency, and cost over time.
3. Leaderboard compares runs only within the same benchmark version and policy revision.
