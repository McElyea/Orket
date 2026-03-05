# Scripts Organization

This folder contains command entrypoints and shared script modules.

## Layout

- `HighTier/`
  - Highest-utility scripts (score 7-10).
  - Most-referenced operational and CI-facing entrypoints.
- `MidTier/`
  - Useful support scripts (score 4-6).
  - General reporting, orchestration, and utility automation.
- `LowTier/`
  - Niche or low-reference scripts (score 1-3).
  - Kept for specific workflows and experiments.
- `quant_sweep/`
  - Reusable quant-sweep package.
  - Provider-aware runtime hooks.
  - Shared sidecar and KPI logic.
- `tiering/`
  - Tier assignment artifacts and score chart.
  - `script_tier_scores.md` and `script_tier_scores.csv`.

Scores are computed from workflow/test/docs references plus recent activity, then grouped by family/dependency so near-duplicate scripts stay together.

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

- LM Studio sanitation uses `scripts/MidTier/lmstudio_model_cache.py`.
- Sweeps only invoke sanitation when provider is `lmstudio`.
- Opaque "one-size-fits-all provider adapters" are intentionally avoided.

## Migration Rule

When adding new script suites:

1. Add a thin `run_*` entrypoint.
2. Put reusable logic in a service module/package.
3. Keep provider-specific branches explicit and testable.
4. Reuse existing shared modules before adding new helpers.

