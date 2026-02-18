# Orket Roadmap

Last updated: 2026-02-17.

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

## Priority 3: Live Benchmark Execution (Active)
Objective: execute the full benchmark task bank (`001`-`100`) through the real Orket card system in repeatable, auditable phases.

Run policy:
1. Execute in 5-task groups to isolate failures and simplify reruns.
2. Use live card runner only (no synthetic pass runner).
3. Keep one scored artifact per phase plus one merged report set.

Live phase command template:
`python scripts/run_determinism_harness.py --task-bank benchmarks/task_bank/v1/tasks.json --runs 1 --venue local-hardware --flow live-card --runner-template "python scripts/live_card_benchmark_runner.py --task {task_file} --venue {venue} --flow {flow} --run-dir {run_dir}" --artifact-glob live_runner_output.log --task-id-min <MIN> --task-id-max <MAX> --output benchmarks/results/live_card_phase_<MIN>_<MAX>_determinism.json`

Score command template:
`python scripts/score_benchmark_run.py --report benchmarks/results/live_card_phase_<MIN>_<MAX>_determinism.json --task-bank benchmarks/task_bank/v1/tasks.json --policy model/core/contracts/benchmark_scoring_policy.json --out benchmarks/results/live_card_phase_<MIN>_<MAX>_scored.json`

Execution phases:
1. Phase 01: `001`-`005`
2. Phase 02: `006`-`010`
3. Phase 03: `011`-`015`
4. Phase 04: `016`-`020`
5. Phase 05: `021`-`025`
6. Phase 06: `026`-`030`
7. Phase 07: `031`-`035`
8. Phase 08: `036`-`040`
9. Phase 09: `041`-`045`
10. Phase 10: `046`-`050`
11. Phase 11: `051`-`055`
12. Phase 12: `056`-`060`
13. Phase 13: `061`-`065`
14. Phase 14: `066`-`070`
15. Phase 15: `071`-`075`
16. Phase 16: `076`-`080`
17. Phase 17: `081`-`085`
18. Phase 18: `086`-`090`
19. Phase 19: `091`-`095`
20. Phase 20: `096`-`100`

Execution progress:
1. Completed: Phase 01-12 (`001`-`060`) on local hardware via live card runner.
2. Next: Phase 13-16 (`061`-`080`).

Acceptance criteria:
1. All 20 phases produce determinism and scored artifacts.
2. Every task exits through live card execution path.
3. Final merged score report has zero failing tasks.

Closeout commands:
1. Full live suite (single-shot):
   - `python scripts/run_live_card_benchmark_suite.py --runs 1 --raw-out benchmarks/results/live_card_100_determinism_report.json --scored-out benchmarks/results/live_card_100_scored_report.json`
2. Live pytest gate:
   - `set ORKET_RUN_BENCHMARK_LIVE_100=1 && python -m pytest tests/live/test_benchmark_task_bank_live.py -q`
