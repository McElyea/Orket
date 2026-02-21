# Orket Roadmap

Last updated: 2026-02-21

## Outcome
Deliver production-ready quantization testing on live Orket runs, with strict telemetry, deterministic summaries, and actionable quant recommendations per hardware fingerprint.

## Status
Current scope is implemented. Ongoing work is regression hardening and operational tuning.

## Guiding Rules (Updated)
1. No guessing: missing provider metadata remains explicit (`TOKEN_COUNT_UNAVAILABLE`, `TIMING_UNAVAILABLE`, `TOKEN_AND_TIMING_UNAVAILABLE`).
2. Phase isolation: model-internal time and wall-clock time are both tracked and never conflated.
3. Identity vs quality: hardware fingerprint identifies environment; `run_quality_status` (`CLEAN`/`POLLUTED`) gates run validity.
4. Adherence as gate: `adherence_score` is the primary quality gate; vibe metrics are optimization signals after gate pass.
5. Reproducibility first: benchmark comparisons are valid only with explicit controls (seed, threads, affinity policy, warmup policy).
6. Preserve runner semantics: all changes are additive instrumentation/reporting, not behavioral rewrites.

## Implemented (Subject to Regression)
1. Live benchmark telemetry includes latency, memory, adherence, token metrics, and vibe metrics.
2. Baseline storage and selection are implemented under `orket_storage/baselines/{test_id}.json` with history records.
3. Quant sweep orchestration is implemented in `scripts/run_quant_sweep.py`.
4. Sweep summary includes per-quant comparisons, baseline quant selection, frontier logic, and recommendation text.
5. Runtime naming migration is in place with backward-compatible aliases for `venue` and `flow`.
6. Regression coverage exists for telemetry normalization and baseline/vibe logic.
7. Canary gate is implemented in quant sweep execution.
8. Run-quality status and polluted-run exclusion are implemented with override policy.
9. Matrix config presets and dry-run plan resolution are implemented.
10. Baseline management CLI now supports list/show/resolve/pin/health/prune.
11. Optional hardware sidecar capture is implemented and joined in sweep summary.
12. CI smoke workflow is added for quant sweep scripts/tests and matrix dry-run.
13. Quant sweep runbook is documented in `docs/QUANT_SWEEP_RUNBOOK.md`.

## Delivery Plan (Remaining Work)

### Milestone 0: Canary Gate
1. Run 10 repetitions of one fixed model/quant/task combo (reference: `llama3.1:8b` + `Q4_K_M` + a standard logic task).
2. Use fixed experimental controls for all 10 runs:
   - Seed value.
   - Thread count.
   - Affinity policy/mask (when supported by OS/runtime).
   - Warmup steps.
3. Record run-level quality state for each run:
   - `run_quality_status`: `CLEAN` or `POLLUTED`.
   - `run_quality_reasons`: machine-readable diagnostics.
4. Block progression to matrix phase unless Canary thresholds pass.

Exit criteria:
1. Adherence variance is `0.0` across the 10-run Canary.
2. Internal latency variance is below agreed threshold (default target: `< 3%`).
3. Missing token/timing telemetry rate is `0%` for Canary.
4. Finalized control profile is documented and reused for matrix runs.

### Phase 1: Strict Telemetry and Run-Quality Enforcement
1. Finalize provider telemetry contract so token counts and timings are normalized at adapter boundaries.
2. Add explicit provider capability flags for true streaming vs monolithic responses.
3. Add orchestration overhead metric:
   - `orchestration_overhead_ratio = (wall_clock_seconds - internal_model_seconds) / wall_clock_seconds`.
4. Add environment quality signals to telemetry:
   - CPU load/saturation snapshots.
   - Effective thread count.
   - Affinity information when available.
5. Add strict status-machine tests for:
   - Zero-token completion.
   - Missing token counts.
   - Missing timings.
   - Partial metadata.

Exit criteria:
1. Every run emits deterministic token status and run-quality status.
2. Throughput metrics are numeric only when valid; otherwise explicit `null` with status reason.
3. Overhead ratio is emitted whenever timing data is available.
4. Run-quality flags correctly detect polluted conditions.

### Phase 2: Matrix Presets and Controlled Execution
1. Add matrix preset config files for common model families and quant ladders.
2. Support per-model quant lists, thresholds, and control profile references without script edits.
3. Add task-bucket presets (logic, refactor, mixed).
4. Add dry-run mode that prints resolved matrix, controls, and expected artifact paths.

Exit criteria:
1. A single command executes the full preset matrix under locked controls.
2. Resolved matrix is reproducible from config + commit SHA + control profile.

### Phase 3: Baseline Operations and Governance
1. Add CLI utilities to inspect, append, and pin baseline references by run ID.
2. Add baseline health checks for stale or incompatible records.
3. Add retention policy controls for baseline history growth.
4. Emit explicit mismatch reasons in summaries when baseline comparison is skipped.

Exit criteria:
1. Operators can manage baselines without editing JSON manually.
2. Baseline mismatches are diagnosable from summary output alone.

### Phase 4: Sweep Summary and Dual Recommendation Engine
1. Finalize summary shape for downstream consumption (`sessions`, `per_quant`, `efficiency_frontier`, `recommendation`).
2. Include strict token telemetry aggregates (`prompt_tokens_per_second`, `generation_tokens_per_second`, status).
3. Emit two deterministic recommendations:
   - `minimum_viable_quant`: first quant (low-to-high precision loss) meeting adherence and latency thresholds.
   - `best_value_quant`: quant with highest utility score under threshold constraints (default utility: `adherence_score / total_latency`).
4. Add deterministic tie-breakers for `best_value_quant`:
   - Higher adherence wins.
   - Then lower latency.
   - Then higher precision quant rank.
5. Emit explicit no-frontier recommendation when no quant passes thresholds.
6. Include experimental controls block in summaries (`seed`, `threads`, `affinity_policy`, `warmup_steps`).

Exit criteria:
1. `sweep_summary.json` can be consumed directly for side-by-side comparisons.
2. Both recommendation outputs are deterministic for identical input data.
3. Summary carries run-quality diagnostics and control metadata needed for audit.

### Phase 5: Hardware Throughput Sidecar (llama-bench)
1. Add optional sidecar execution for llama-bench to capture raw hardware throughput.
2. Store sidecar output separately from task-adherence telemetry, then join at summary time.
3. Do not use sidecar numbers as pass/fail gates; keep them diagnostic.
4. Add docs mapping sidecar metrics to Orket metrics (prefill/decode vs wall-clock).

Exit criteria:
1. Sidecar output is available per sweep session when enabled.
2. Summary clearly distinguishes hardware throughput from task efficacy.

### Phase 6: Operational Rollout and CI
1. Add smoke matrix job for CI with a minimal model/quant set.
2. Add nightly or on-demand full matrix run for richer hardware/regression data.
3. Publish runbook for local and CI execution with troubleshooting paths.
4. Capture and track stability KPIs (determinism rate, missing telemetry rate, polluted-run rate, frontier success rate).

Exit criteria:
1. CI verifies schema stability and command health.
2. Team can run full sweeps reproducibly from docs.
3. Clean-run SLOs are met:
   - Missing telemetry rate `< 1%`.
   - Determinism `100%` on fixed-seed logic tasks.
   - Polluted-run rate remains below agreed threshold for controlled runs.

## Risks and Mitigations
1. Risk: Provider metadata differences cause inconsistent TPS calculations.
   Mitigation: enforce adapter-level normalization and strict status fallback.
2. Risk: Background system load pollutes latency variance and frontier decisions.
   Mitigation: enforce run-quality status and controls metadata; exclude polluted runs from recommendations by default.
3. Risk: Baseline drift from prompt/task changes creates false comparisons.
   Mitigation: lock baseline matching on `test_id`, `hardware_fingerprint`, and `task_revision`.
4. Risk: Summary schema drift breaks downstream readers.
   Mitigation: add contract tests and backward-compatible field additions only.

## Execution Commands (Reference)
1. Single sweep:
   `python scripts/run_quant_sweep.py --model-id qwen2.5-coder:7b --quant-tags Q8_0,Q6_K,Q4_K_M --runs 3 --task-bank benchmarks/task_bank/v2_realworld/tasks.json`
2. Save a baseline from a known-good run:
   `python scripts/live_card_benchmark_runner.py --task <task-json> --save-baseline`
3. Determinism harness output:
   `python scripts/run_determinism_harness.py --task-bank <task-bank> --runs 3 --output benchmarks/results/determinism_report.json`
4. Canary-style repeat run (example pattern):
   `python scripts/run_determinism_harness.py --task-bank <task-bank> --task-limit 1 --runs 10 --output benchmarks/results/canary_report.json`
