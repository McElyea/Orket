# Orket Roadmap

Last updated: 2026-02-14.

## Operating Constraints (Current)
1. Monolith remains default; microservices are pilot-only and must be explicitly enabled.
2. Frontend policy is Vue-only when a frontend is required.
3. iDesign is backburnered and not a current gate.
4. Small-task minimum team is one builder (`coder` or `architect`) plus one mandatory `code_reviewer`.
5. Replan limit is terminal: `replan_count > 3` halts with rejection semantics.

## Priority 1: Controlled Microservices Pilot
Objective: run controlled microservices pilots with measurable side-by-side evidence while keeping monolith as default.

### P1.1 Pilot Gating Rule
1. Keep monolith as runtime default until microservices pilot is stable for two consecutive batches.
2. Stability means:
   - microservices pass rate >= monolith pass rate for the same matrix slice, and
   - runtime failure/reviewer rejection do not regress.
3. Acceptance criteria:
   - Gate decision is mechanical and artifact-backed.
   - Decision is reproducible from saved artifacts.

### P1.2 Runtime Policy Alignment
1. Ensure runtime policy surfaces pilot state clearly:
   - unlocked state
   - default mode
   - selected mode
2. Ensure UI/API controls map directly to enforced runtime behavior.
3. Acceptance criteria:
   - policy endpoint and orchestrator behavior are consistent under env + settings combinations.
4. Baseline evidence artifact available:
   - `benchmarks/results/architecture_pilot_matrix.json`

## Priority 2: Packaging Readiness Follow-Through
Objective: maintain deterministic local-first packaging quality while pilot work proceeds.

### P2.1 Weekly Determinism Proof
1. Run and keep green:
   - `python -m pytest tests -q`
   - `python scripts/check_dependency_direction.py`
   - `python scripts/check_volatility_boundaries.py`
2. Keep matrix + unlock evidence fresh:
   - `python scripts/run_monolith_variant_matrix.py --execute --out benchmarks/results/monolith_variant_matrix.json`
   - `python -m scripts.report_live_acceptance_patterns --matrix benchmarks/results/monolith_variant_matrix.json`
   - `python scripts/check_monolith_readiness_gate.py --matrix benchmarks/results/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only`
   - `python scripts/check_microservices_unlock.py --matrix benchmarks/results/monolith_variant_matrix.json --readiness-policy model/core/contracts/monolith_readiness_policy.json --unlock-policy model/core/contracts/microservices_unlock_policy.json --live-report benchmarks/results/live_acceptance_patterns.json --out benchmarks/results/microservices_unlock_check.json`
   - `python scripts/decide_microservices_pilot.py --unlock-report benchmarks/results/microservices_unlock_check.json --out benchmarks/results/microservices_pilot_decision.json`

## Backburner (Not Active)
1. Additional frontend frameworks beyond Vue.
2. iDesign-first enforcement.
3. Broad architecture expansion beyond controlled microservices pilots.
