# Orket Roadmap

Last updated: 2026-02-15.

## Operating Constraints (Current)
1. Orket engine loop remains the runtime; storage backend is pluggable.
2. Monolith remains default; microservices stay policy-controlled.
3. Frontend policy is Vue-only when a frontend is required.
4. iDesign is backburnered and not an active gate.
5. Small-task minimum team is one builder (`coder` or `architect`) plus one mandatory `code_reviewer`.
6. Replan limit is terminal: `replan_count > 3` halts with rejection semantics.

## Priority 1: Gitea-Backed State Adapter (Top Priority)
Objective: add a remote state store + work queue surface via Gitea without changing the Orket runtime loop.

### P1-A. Rollout Strategy
1. Phase 2: hardening pass with contention/failure injection tests.
   - Required gate command:
     - `python scripts/check_gitea_state_pilot_readiness.py --out benchmarks/results/gitea_state_pilot_readiness.json --require-ready`
   - Startup validation must block `state_backend_mode=gitea` unless pilot enablement and readiness are satisfied.
2. Phase 3: multi-runner support (after Phase 2 pass criteria).
4. Acceptance criteria:
   - `local` remains default and stable.
   - `gitea` remains explicitly marked experimental until contention suite is green.
   - No features depend exclusively on gitea backend semantics until Phase 3 is complete.

## Priority 2: Determinism Maintenance (Recurring)
Objective: keep current quality gates green while Priority 1 lands.

1. Keep these commands green:
   - `python -m pytest tests -q`
   - `python scripts/check_dependency_direction.py`
   - `python scripts/check_volatility_boundaries.py`
2. Keep readiness artifacts fresh:
   - `python scripts/run_monolith_variant_matrix.py --execute --out benchmarks/results/monolith_variant_matrix.json`
   - `python -m scripts.report_live_acceptance_patterns --matrix benchmarks/results/monolith_variant_matrix.json`
   - `python scripts/check_monolith_readiness_gate.py --matrix benchmarks/results/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only`

## Priority 3: Architecture Pilot Monitoring (Recurring)
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
