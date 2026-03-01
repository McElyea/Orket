# Quant Sweep Runbook

Last reviewed: 2026-02-27

## Purpose
Run reproducible quantization sweeps with deterministic summary artifacts and policy gates.

## Core Inputs
1. Matrix config (default): `benchmarks/configs/quant_sweep_common_sessions.json`
2. Optional configs:
   - `benchmarks/configs/quant_sweep_logic_only.json`
   - `benchmarks/configs/quant_sweep_refactor_heavy.json`
   - `benchmarks/configs/quant_sweep_mixed.json`

## Dry Run
```powershell
python scripts/run_quant_sweep.py `
  --model-id placeholder `
  --quant-tags Q8_0 `
  --matrix-config benchmarks/configs/quant_sweep_common_sessions.json `
  --dry-run
```

## Execute Sweep
```powershell
python scripts/run_quant_sweep.py `
  --model-id placeholder `
  --quant-tags Q8_0 `
  --matrix-config benchmarks/configs/quant_sweep_common_sessions.json `
  --summary-out benchmarks/results/quant_sweep/sweep_summary.json
```

## KPI and Gate Checks
1. KPI extraction:
```powershell
python scripts/quant_sweep_kpi_report.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out benchmarks/results/quant_sweep/sweep_kpis.json
```
2. KPI gate:
```powershell
python scripts/check_quant_sweep_kpis.py --summary benchmarks/results/quant_sweep/sweep_summary.json
```
3. Lab guard diagnostics:
```powershell
python scripts/check_lab_guards.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --cooldown-target-c 50 `
  --vram-profile safe `
  --allow-skip
```

## Reporting Artifacts
1. Markdown/scatter report:
```powershell
python scripts/render_quant_sweep_report.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out-md benchmarks/results/quant_sweep/sweep_report.md `
  --out-scatter benchmarks/results/quant_sweep/sweep_scatter.json
```
2. Frontier explorer artifact:
```powershell
python scripts/quant_frontier_explorer.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out benchmarks/results/quant_sweep/frontier_explorer.json `
  --provenance-ref local-run:manual `
  --storage-root .orket/durable/diagnostics/frontiers
```

## Context and Thermal Extensions
1. Context sweep orchestrator:
```powershell
python scripts/run_context_sweep.py `
  --contexts 4096,8192,16384 `
  --model-id qwen2.5-coder:7b `
  --quant-tags Q8_0 `
  --task-bank benchmarks/task_bank/v2_realworld/tasks.json `
  --execution-lane lab `
  --vram-profile safe `
  --out-dir benchmarks/results/context_sweep
```
2. Thermal profiler:
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
  --storage-root .orket/durable/diagnostics/thermal_profiles
```

## CI Workflows (Gitea)
1. Smoke: `.gitea/workflows/quant-sweep-smoke.yml`
2. Nightly: `.gitea/workflows/quant-sweep-nightly.yml`
3. Full self-hosted: `.gitea/workflows/quant-sweep-full-selfhosted.yml`

## Notes
1. Matrix config can override `--model-id` and `--quant-tags` values.
2. Polluted rows are excluded from frontier by default.
3. Sidecar metrics are diagnostics-only, not pass/fail gate inputs.
