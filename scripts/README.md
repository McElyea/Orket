# Scripts Organization

This folder contains command entrypoints and shared script modules.

## Layout

- `acceptance/`, `benchmarks/`, `context/`, `explorer/`, `extensions/`
- `gitea/`, `governance/`, `nervous_system/`, `odr/`, `ops/`
- `protocol/`, `providers/`, `quant/`, `replay/`, `security/`, `streaming/`
  - Functional script domains. Entrypoints are grouped by what they do, not by score band.
- `quant_sweep/`
  - Reusable quant-sweep package.
  - Provider-aware runtime hooks.
  - Shared sidecar and KPI logic.
- `tiering/`
  - Score artifacts and legacy score-band metadata.
  - `script_tier_scores.md` and `script_tier_scores.csv`.

Scores are still computed from workflow/test/docs references plus recent activity, then grouped by family/dependency so near-duplicate scripts stay together.

## Quant Sweep Package

`quant_sweep` is the reusable interface for quant workflows:

- `quant_sweep.config`
  - CLI/model matrix defaults and provider sanitation plan.
- `quant_sweep.runner`
  - Main orchestration pipeline for a sweep run.
- `quant_sweep.canary`
  - Determinism canary gate logic.
- `quant_sweep.sidecar`
  - Hardware sidecar parsing/output contract.
- `quant_sweep.metrics`
  - Frontier/validity logic and KPI aggregation.
- `quant_sweep.runtime`
  - Shared subprocess and JSON helpers.

Entry scripts should depend on this package instead of duplicating quant orchestration logic.

## Provider Boundaries

Provider-specific behavior stays explicit:

- LM Studio sanitation uses `scripts/providers/lmstudio_model_cache.py`.
- Sweeps only invoke sanitation when provider is `lmstudio`.
- Opaque "one-size-fits-all provider adapters" are intentionally avoided.

## Provider-Model Quickstart

Provider/model IDs are not interchangeable between Ollama and LM Studio.
Use provider-aware helpers to avoid mismatches:

- Discover provider-compatible models:
  - `python scripts/providers/list_real_provider_models.py --provider lmstudio --recommend-model`
  - `python scripts/providers/list_real_provider_models.py --provider ollama --recommend-model`
- Validate real-provider wiring with optional auto model selection:
  - `python scripts/providers/check_model_provider_preflight.py --provider lmstudio --auto-select-model`
- Run the quant tuner with provider-aware model resolution (no setup wizard required):
  - `python scripts/quant/tune_quant_sweep_provider_ready.py --matrix-config <path> --provider lmstudio --auto-model-count 1`

## Migration Rule

When adding new script suites:

1. Add a thin `run_*` entrypoint.
2. Put reusable logic in a service module/package.
3. Keep provider-specific branches explicit and testable.
4. Reuse existing shared modules before adding new helpers.
