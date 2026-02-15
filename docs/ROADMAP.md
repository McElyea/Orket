# Orket Roadmap

Last updated: 2026-02-15.

## Operating Constraints (Current)
1. Monolith remains default; microservices are controlled via explicit runtime mode.
2. Frontend policy is Vue-only when a frontend is required.
3. iDesign is backburnered and not an active gate.
4. Small-task minimum team is one builder (`coder` or `architect`) plus one mandatory `code_reviewer`.
5. Replan limit is terminal: `replan_count > 3` halts with rejection semantics.

## Priority A: Ongoing Determinism Gate (Active)
Objective: keep packaging/runtime quality mechanically green every cycle.

### A1. Determinism Proof (Recurring)
1. Keep these commands green on each pass:
   - `python -m pytest tests -q`
   - `python scripts/check_dependency_direction.py`
   - `python scripts/check_volatility_boundaries.py`
2. Refresh readiness artifacts:
   - `python scripts/run_monolith_variant_matrix.py --execute --out benchmarks/results/monolith_variant_matrix.json`
   - `python -m scripts.report_live_acceptance_patterns --matrix benchmarks/results/monolith_variant_matrix.json`
   - `python scripts/check_monolith_readiness_gate.py --matrix benchmarks/results/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only`
   - `python scripts/check_microservices_unlock.py --matrix benchmarks/results/monolith_variant_matrix.json --readiness-policy model/core/contracts/monolith_readiness_policy.json --unlock-policy model/core/contracts/microservices_unlock_policy.json --live-report benchmarks/results/live_acceptance_patterns.json --out benchmarks/results/microservices_unlock_check.json`
   - `python scripts/decide_microservices_pilot.py --unlock-report benchmarks/results/microservices_unlock_check.json --out benchmarks/results/microservices_pilot_decision.json`

## Priority B: Controlled Architecture Pilot Monitoring (Active)
Objective: keep side-by-side monolith vs microservices evidence current and mechanical.

### B1. Pilot Matrix Refresh
1. Regenerate pilot matrix with previous artifact rotation:
   - `python scripts/run_architecture_pilot_matrix.py --execute --out benchmarks/results/architecture_pilot_matrix.json --rotate-prev-out benchmarks/results/architecture_pilot_matrix_prev.json`
2. Evaluate consecutive stability:
   - `python scripts/check_microservices_pilot_stability.py --artifacts benchmarks/results/architecture_pilot_matrix_prev.json benchmarks/results/architecture_pilot_matrix.json --required-consecutive 2 --out benchmarks/results/microservices_pilot_stability_check.json`
3. Keep runtime policy exposure aligned:
   - `microservices_unlocked` and `microservices_pilot_stable` must remain present in runtime policy output.

## Backburner (Not Active)
1. Additional frontend frameworks beyond Vue.
2. iDesign-first enforcement.
3. Architecture expansion beyond controlled microservices monitoring.
