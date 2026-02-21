# Quant Sweep Runbook

## Purpose
Run reproducible quantization sweeps with strict telemetry, canary gating, and optional hardware sidecar diagnostics.

## Preset Matrix
Use the shared preset config:

`benchmarks/configs/quant_sweep_common_sessions.json`

Additional preset packs:
1. `benchmarks/configs/quant_sweep_logic_only.json`
2. `benchmarks/configs/quant_sweep_refactor_heavy.json`
3. `benchmarks/configs/quant_sweep_mixed.json`

## Dry Run
Resolve matrix, controls, and artifacts without executing model runs:

```powershell
python scripts/run_quant_sweep.py `
  --model-id placeholder `
  --quant-tags Q8_0 `
  --matrix-config benchmarks/configs/quant_sweep_common_sessions.json `
  --dry-run
```

Expected output includes:
1. `commit_sha`
2. `models`, `quants`
3. `experimental_controls`
4. `canary` settings
5. sidecar settings if configured

## Full Sweep
Run preset matrix:

```powershell
python scripts/run_quant_sweep.py `
  --model-id placeholder `
  --quant-tags Q8_0 `
  --matrix-config benchmarks/configs/quant_sweep_common_sessions.json `
  --summary-out benchmarks/results/quant_sweep/sweep_summary.json
```

Notes:
1. `--model-id` and `--quant-tags` are still required CLI args; matrix config overrides them.
2. Canary gate aborts sweep if thresholds fail.
3. Polluted quant rows are excluded from frontier/recommendations by default.
4. Sweep artifacts include `execution_lane` and `vram_profile` labels.

Recommended lane/profile labels:
1. `--execution-lane ci --vram-profile safe` for deterministic non-physics CI work.
2. `--execution-lane lab --vram-profile safe` for long local experiment sessions.
3. `--execution-lane lab --vram-profile balanced|stress` for boundary testing.

## CI Workflow Modes
1. Smoke workflow: `.github/workflows/quant-sweep-smoke.yml`
   - Deterministic and model-free.
   - Runs unit tests + matrix dry-run only.
2. Full self-hosted workflow: `.github/workflows/quant-sweep-full-selfhosted.yml`
   - Executes real sweep runs on self-hosted hardware.
   - Produces summary, KPI report, sidecar artifacts, and provenance metadata.
   - Fails on KPI policy violations.

## Polluted Override
Include polluted rows in frontier logic:

```powershell
python scripts/run_quant_sweep.py `
  --model-id qwen2.5-coder:7b `
  --quant-tags Q8_0,Q6_K,Q4_K_M `
  --task-bank benchmarks/task_bank/v2_realworld/tasks.json `
  --allow-polluted-frontier
```

## Optional Hardware Sidecar
Attach per-quant hardware diagnostics command:

```powershell
python scripts/run_quant_sweep.py `
  --model-id qwen2.5-coder:7b `
  --quant-tags Q8_0,Q6_K `
  --task-bank benchmarks/task_bank/v2_realworld/tasks.json `
  --hardware-sidecar-template "python scripts/fake_llama_bench.py --model {model_id} --quant {quant_tag}" `
  --hardware-sidecar-timeout-sec 120
```

Results are stored under:

`benchmarks/results/quant_sweep/sidecar/<model>/<quant>_hardware_sidecar.json`

Profile-based sidecar mode:

```powershell
python scripts/run_quant_sweep.py `
  --model-id qwen2.5-coder:7b `
  --quant-tags Q8_0,Q6_K `
  --task-bank benchmarks/task_bank/v2_realworld/tasks.json `
  --hardware-sidecar-profile nvidia `
  --sidecar-profiles-config benchmarks/configs/sidecar_profiles.json
```

Profile compatibility notes:
1. `nvidia` uses `scripts/sidecar_probe.py --backend nvidia` (queries `nvidia-smi` when available).
2. `amd` uses `scripts/sidecar_probe.py --backend amd` (fallback numeric payload; extend with ROCm-specific probes as needed).
3. `cpu_only` uses `scripts/sidecar_probe.py --backend cpu` (diagnostic placeholder payload).

## Sidecar Metric Mapping
Use sidecar as hardware diagnostics only; do not gate pass/fail on sidecar values.
1. Sidecar decode throughput (`generation_tps`) maps to Orket `token_metrics.throughput.generation_tokens_per_second`.
2. Sidecar prefill throughput maps to Orket `token_metrics.throughput.prompt_tokens_per_second` when provider timings are present.
3. Sidecar totals are compared against Orket wall-clock metrics for orchestration overhead analysis, not quality scoring.
4. If sidecar and Orket diverge significantly, trust Orket for task efficacy and use sidecar for hardware investigation.

## Stability KPI Tracking
Sweep summaries include `stability_kpis`:
1. `determinism_rate`
2. `missing_telemetry_rate`
3. `polluted_run_rate`
4. `frontier_success_rate`

Extract KPI report:

```powershell
python scripts/quant_sweep_kpi_report.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out benchmarks/results/quant_sweep/sweep_kpis.json
```

## Operator Visualization Report
Generate operator-facing report artifacts (scatter dataset + markdown):

```powershell
python scripts/render_quant_sweep_report.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out-md benchmarks/results/quant_sweep/sweep_report.md `
  --out-scatter benchmarks/results/quant_sweep/sweep_scatter.json
```

Include invalid rows in report views only:

```powershell
python scripts/render_quant_sweep_report.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out-md benchmarks/results/quant_sweep/sweep_report.md `
  --out-scatter benchmarks/results/quant_sweep/sweep_scatter.json `
  --include-invalid
```

## Quant Frontier Explorer Artifact
Generate a comparable frontier artifact keyed by hardware fingerprint + lane + profile:

```powershell
python scripts/quant_frontier_explorer.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out benchmarks/results/quant_sweep/frontier_explorer.json `
  --provenance-ref local-run:manual `
  --storage-root orket_storage/frontiers
```

## Context Ceiling Finder Artifact
Generate safe context ceiling recommendation from context sweep summaries:

```powershell
python scripts/context_ceiling_finder.py `
  --contexts 4096,8192,16384 `
  --summary-template benchmarks/results/context_sweep/context_{context}.json `
  --adherence-min 0.95 `
  --ttft-ceiling-ms 250 `
  --decode-floor-tps 20 `
  --execution-lane lab `
  --vram-profile safe `
  --provenance-ref local-run:manual `
  --out benchmarks/results/context_sweep/context_ceiling.json `
  --storage-root orket_storage/context_ceilings
```

## Thermal Stability Profiler Artifact
Generate thermal stability recommendation from repeated run summaries:

```powershell
python scripts/thermal_stability_profiler.py `
  --summaries benchmarks/results/quant_sweep/run1.json,benchmarks/results/quant_sweep/run2.json,benchmarks/results/quant_sweep/run3.json `
  --cooldown-target-c 50 `
  --polluted-thermal-threshold-c 85 `
  --monotonic-window 2 `
  --execution-lane lab `
  --vram-profile safe `
  --provenance-ref local-run:manual `
  --out benchmarks/results/thermal/thermal_profile.json `
  --storage-root orket_storage/thermal_profiles
```

## Explorer Schema Contract Check
Validate explorer artifact required fields in CI or local runs:

```powershell
python scripts/check_explorer_schema_contracts.py `
  --frontier benchmarks/results/quant_sweep/full_frontier_explorer.json `
  --context benchmarks/results/context_sweep/context_ceiling.json `
  --thermal benchmarks/results/thermal/thermal_profile.json
```

## Baseline Operations
List baselines:

```powershell
python scripts/manage_baselines.py list --storage-root orket_storage/baselines
```

Resolve for current run:

```powershell
python scripts/manage_baselines.py resolve `
  --storage-root orket_storage/baselines `
  --test-id 001 `
  --hardware-fingerprint "<fingerprint>" `
  --task-revision v1
```

Health summary:

```powershell
python scripts/manage_baselines.py health `
  --storage-root orket_storage/baselines `
  --hardware-fingerprint "<fingerprint>" `
  --task-revision v1
```

Prune old history while keeping newest 3:

```powershell
python scripts/manage_baselines.py prune `
  --storage-root orket_storage/baselines `
  --keep-last 3
```

Pin a baseline record so prune never removes it:

```powershell
python scripts/manage_baselines.py pin-baseline `
  --storage-root orket_storage/baselines `
  --test-id 001 `
  --baseline-ref <test-run-id>
```

Unpin a baseline record:

```powershell
python scripts/manage_baselines.py unpin-baseline `
  --storage-root orket_storage/baselines `
  --test-id 001 `
  --baseline-ref <test-run-id>
```

Retention policy defaults:
1. Keep newest 10 unpinned records per test id (`--keep-last 10`).
2. Pinned records are retained regardless of age.
3. Run prune weekly in operations/CI maintenance windows.
