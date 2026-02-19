# Orket Roadmap

Last updated: 2026-02-19.

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
1. Completed: Phase 01-20 (`001`-`100`) on local hardware via live card runner.
2. Status: 100/100 live card-path tasks executed and scored with zero failing tasks.

Acceptance criteria:
1. All 20 phases produce determinism and scored artifacts.
2. Every task exits through live card execution path.
3. Final merged score report has zero failing tasks.

Closeout commands:
1. Full live suite (single-shot):
   - `python scripts/run_live_card_benchmark_suite.py --runs 1 --raw-out benchmarks/results/live_card_100_determinism_report.json --scored-out benchmarks/results/live_card_100_scored_report.json`
2. Live pytest gate:
   - `set ORKET_RUN_BENCHMARK_LIVE_100=1 && python -m pytest tests/live/test_benchmark_task_bank_live.py -q`

## Priority 4: iDesign Decoupling and Crash Hardening (Active)
Objective: remove iDesign backdoor coupling from default runtime paths and prevent governance over-escalation for recoverable tool/runtime failures.

Observed failures from `workspace/default/orket_crash.log` (2026-02-17):
1. Repeated terminal governance crashes: `iDesign Violation: Governance violations: ['Tool read_file failed: File not found']`
2. iDesign AST syntax violations still raised as terminal governance despite iDesign backburner policy.
3. Runtime crash unrelated to governance: `NameError: name 'Path' is not defined` in `orket/domain/bug_fix_phase.py`.
4. Policy strictness mismatch: small-project card fails terminally when required `code_reviewer` seat is missing.

Plan:
1. De-couple iDesign wording and exception routing from default governance path:
   - Replace default failure message prefix from `iDesign Violation:` to neutral `Governance Violation:` when `architecture_governance.idesign` is false.
   - Keep iDesign-specific labeling only when iDesign is explicitly enabled by epic policy.
2. Reclassify missing-file read failures as recoverable turn failures instead of terminal governance violations:
   - Treat `Tool read_file failed: File not found` as actionable context/read-scope issue.
   - Route first occurrence to corrective reprompt with explicit recovery guidance (confirm path, list directory, create file if task allows).
   - Escalate to terminal only after deterministic repeated non-progress threshold is exceeded.
3. Gate iDesign AST enforcement behind explicit iDesign enablement:
   - When iDesign is disabled/backburnered, skip AST iDesign validators entirely for normal card paths.
   - Add a hard assertion in evaluator nodes that iDesign AST violations cannot surface when mode is disabled.
4. Add preflight and guardrail checks before agent tool loop:
   - Validate required read paths exist (or are creatable) and emit deterministic warning artifacts instead of immediate governance failure.
   - Inject task-context fallback for missing optional inputs so first turn does not fail on absent files.
5. Fix concrete runtime defects found in crash log:
   - Patch `orket/domain/bug_fix_phase.py` to import/use `Path` correctly and add regression test.
   - Improve small-task team policy handling:
     - preflight-reject with actionable message before turn execution, or
     - auto-inject `code_reviewer` seat where policy requires it.
6. Add targeted regression tests:
   - `read_file` missing path -> corrective reprompt path, not immediate governance terminal.
   - iDesign disabled -> no iDesign AST violation message/exceptions.
   - bug-fix phase start path logging does not raise `NameError`.
   - small-team policy violation caught in preflight with deterministic remediation output.
7. Add acceptance gates for this priority:
   - `python -m pytest tests/application/test_turn_executor_middleware.py -q`
   - `python -m pytest tests/integration/test_idesign_enforcement.py -q`
   - `python -m pytest tests/integration/test_engine_boundaries.py -q`
   - `python -m pytest tests -q`

Exit criteria:
1. Zero occurrences of `iDesign Violation: Governance violations: ['Tool read_file failed: File not found']` across two consecutive live runs.
2. Zero iDesign AST violations when `architecture_governance.idesign=false`.
3. Bug-fix phase no longer throws `NameError: Path`.
4. Determinism/benchmark pipelines remain green after decoupling changes.
