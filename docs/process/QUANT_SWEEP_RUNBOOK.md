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
python scripts/MidTier/run_quant_sweep.py `
  --model-id placeholder `
  --quant-tags Q8_0 `
  --matrix-config benchmarks/configs/quant_sweep_common_sessions.json `
  --dry-run
```

## Execute Sweep
```powershell
python scripts/MidTier/run_quant_sweep.py `
  --model-id placeholder `
  --quant-tags Q8_0 `
  --matrix-config benchmarks/configs/quant_sweep_common_sessions.json `
  --summary-out benchmarks/results/quant_sweep/sweep_summary.json
```

## Short Preflight Tuning
Use the short tuner before long sweeps to select stable canary task IDs and per-model row-overhead thresholds.

```powershell
python scripts/MidTier/tune_quant_sweep_short.py `
  --matrix-config benchmarks/configs/qwen35_logic_sentry.json `
  --models qwen3.5-0.8b,qwen3.5-2b,qwen3.5-4b `
  --candidate-task-ids 8,9 `
  --probe-quant-tag Q8_0 `
  --canary-runs 3 `
  --probe-runs 1 `
  --validate-all-quants `
  --summary-root benchmarks/results/quant_sweep/tuning/preflight_qwen35
```

Read `tuning_manifest.json` under `--summary-root` and apply each model's `recommended_overrides` in the long-run matrix config.
The tuner now also writes `convergence_report.json` and includes a `convergence` block in `tuning_manifest.json` with the auto-evaluated `overall_decision` (`STOP|CONTINUE`).

## Tuning Convergence Check
Use this to decide whether to stop tuning (plateau) or keep running short probes.

```powershell
python scripts/MidTier/check_quant_tuning_convergence.py `
  --summary-root benchmarks/results/quant_sweep/tuning `
  --models qwen3.5-27b,qwen3.5-35b-a3b,qwen/qwen3.5-9b `
  --window 3 `
  --score-epsilon 0.05 `
  --override-epsilon 0.01 `
  --out benchmarks/results/quant_sweep/tuning/convergence_report.json
```

Decision rules:
1. `STOP`: within the window, best task is stable, score stays within epsilon, overrides stay within epsilon, and probes passed.
2. `CONTINUE`: metrics still drifting or failed probes appear in the window.
3. `INSUFFICIENT_DATA`: not enough runs for the selected window.

## KPI and Gate Checks
1. KPI extraction:
```powershell
python scripts/MidTier/quant_sweep_kpi_report.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out benchmarks/results/quant_sweep/sweep_kpis.json
```
2. KPI gate:
```powershell
python scripts/MidTier/check_quant_sweep_kpis.py --summary benchmarks/results/quant_sweep/sweep_summary.json
```
3. Lab guard diagnostics:
```powershell
python scripts/HighTier/check_lab_guards.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --cooldown-target-c 50 `
  --vram-profile safe `
  --allow-skip
```

## Reporting Artifacts
1. Markdown/scatter report:
```powershell
python scripts/MidTier/render_quant_sweep_report.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out-md benchmarks/results/quant_sweep/sweep_report.md `
  --out-scatter benchmarks/results/quant_sweep/sweep_scatter.json
```
2. Frontier explorer artifact:
```powershell
python scripts/MidTier/quant_frontier_explorer.py `
  --summary benchmarks/results/quant_sweep/sweep_summary.json `
  --out benchmarks/results/quant_sweep/frontier_explorer.json `
  --provenance-ref local-run:manual `
  --storage-root .orket/durable/diagnostics/frontiers
```

## Context and Thermal Extensions
1. Context sweep orchestrator:
```powershell
python scripts/MidTier/run_context_sweep.py `
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
python scripts/MidTier/thermal_stability_profiler.py `
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
4. Matrix config optional `runtime_env` object is injected into canary + sweep subprocess env for backend selection (for example LM Studio).
5. Sweep `model_id` is propagated to role model env vars (`ORKET_MODEL_CODER`, `ORKET_MODEL_ARCHITECT`, etc.) unless already set.

## LM Studio Endpoint Policy
1. Orket inference path uses OpenAI-compatible endpoints:
   - `GET /v1/models` for model discovery
   - `POST /v1/chat/completions` for generation
2. LM Studio native endpoints are operator-only control paths:
   - `POST /api/v1/models/load` to pre-load a model before canary/sweep
   - `POST /api/v1/models/download` for model provisioning workflows
3. Do not route benchmark inference to `POST /api/v1/chat`; it expects `input` payload style and is not message-compatible with Orket's current runtime.
4. `ORKET_LLM_OPENAI_BASE_URL` is used as configured. If it points to `/api/v1`, OpenAI-compatible chat-completions paths will not be auto-rewritten.
5. OpenAI-compatible provider calls are strict: message roles must be one of `system|user|assistant|tool`; invalid roles fail fast and must be normalized upstream.
