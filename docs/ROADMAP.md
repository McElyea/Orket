# Orket Roadmap

Last updated: 2026-02-15.

## Operating Constraints (Current)
1. Execution priority is monolith delivery reliability.
2. New project architecture is monolith-only for now; microservices stay locked.
3. Frontend policy is Vue-only when a frontend is required.
4. iDesign is backburnered and not a gating requirement for current roadmap execution.
5. Small-task minimum team is:
   - one builder (`coder` or `architect` variant)
   - one `code_reviewer` (mandatory, never self-review)
6. Replan limit is terminal:
   - `replan_count > 3` halts with terminal failure/rejection semantics.

## Priority B: Microservices Unlock (Locked Until A Complete)
Objective: expand architecture options only after monolith reliability is proven.

### B1. Unlock Criteria
1. Phase A readiness gate must pass.
2. Benchmark matrix must show stable orchestration behavior across project types.
3. Replan/rejection governance must remain stable in production-like runs.

### B2. Controlled Microservices Introduction
1. Add microservices-specific scaffolding/dependency/deployment/runtime verification profiles.
2. Keep monolith default until microservices benchmarks meet quality thresholds.

## Backburner (Not Active)
1. iDesign-first enforcement or iDesign-specific mandatory flows.
2. Additional frontend frameworks beyond Vue.
3. Broad architecture expansion before microservices unlock criteria pass.

## Execution Plan (Remaining)
1. Run executed matrix and live acceptance report artifacts (not plan-only) and re-run unlock checker with `--require-unlocked`.
2. If unlock passes, enable microservices explicitly via `ORKET_ENABLE_MICROSERVICES=true` for controlled pilots.
3. Keep monolith as default until pilot metrics are stable.

## Weekly Proof (Required)
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python scripts/run_monolith_variant_matrix.py --out benchmarks/results/monolith_variant_matrix.json`
5. `python scripts/check_monolith_readiness_gate.py --matrix benchmarks/results/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only`
6. `python scripts/check_microservices_unlock.py --matrix benchmarks/results/monolith_variant_matrix.json --readiness-policy model/core/contracts/monolith_readiness_policy.json --unlock-policy model/core/contracts/microservices_unlock_policy.json --out benchmarks/results/microservices_unlock_check.json`
7. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
8. `python -m scripts.report_live_acceptance_patterns --matrix benchmarks/results/monolith_variant_matrix.json`
