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

Provider-specific behavior stays explicit, but run-path provider/model preparation now shares one authority path:

- Canonical provider runtime target resolution lives in `orket/runtime/provider_runtime_target.py`.
- Runtime entrypoints and provider verification scripts should reuse that module instead of duplicating provider aliasing, base-URL selection, model ranking, or local warmup logic.
- LM Studio sanitation uses `scripts/providers/lmstudio_model_cache.py`.
- Sweeps only invoke sanitation when provider is `lmstudio`.
- Provider-specific execution still stays explicit after target resolution (for example Ollama chat versus OpenAI-compatible chat/stream behavior).

## Provider-Model Quickstart

Provider/model IDs are not interchangeable between Ollama and LM Studio.
Use provider-aware helpers to avoid mismatches:

- Discover provider-compatible models:
  - `python scripts/providers/list_real_provider_models.py --provider lmstudio --recommend-model`
  - `python scripts/providers/list_real_provider_models.py --provider ollama --recommend-model`
- Validate real-provider wiring with optional auto model selection:
  - `python scripts/providers/check_model_provider_preflight.py --provider lmstudio --auto-select-model`
  - For local verification, preflight now uses `lms ls` / `lms ps` / `lms load` and `ollama list` as warmup inventory sources so it can auto-select a runnable installed model and load a local LM Studio model when needed.
- Run the quant tuner with provider-aware model resolution (no setup wizard required):
  - `python scripts/quant/tune_quant_sweep_provider_ready.py --matrix-config <path> --provider lmstudio --auto-model-count 1`

## Runtime Truth Governance

Runtime truth hardening scripts are grouped in `scripts/governance/` and are intended to run as direct script entrypoints (`python scripts/governance/<name>.py`).

- Contract/gate checks:
  - `run_runtime_truth_acceptance_gate.py`
  - `check_runtime_truth_contract_drift.py`
  - `check_model_profile_bios.py`
  - `check_interrupt_semantics_policy.py`
  - `check_idempotency_discipline_policy.py`
  - `check_artifact_provenance_block_policy.py`
  - `check_operator_override_logging_policy.py`
  - `check_demo_production_labeling_policy.py`
  - `check_human_correction_capture_policy.py`
  - `check_sampling_discipline_guide.py`
  - `check_execution_readiness_rubric.py`
  - `check_release_confidence_scorecard.py`
  - `check_feature_flag_expiration_policy.py`
  - `check_workspace_hygiene_rules.py`
  - `check_canonical_examples_library.py`
  - `check_environment_parity_checklist.py`
  - `check_runtime_boundary_audit_checklist.py`
  - `check_retry_classification_policy.py`
  - `check_structured_warning_policy.py`
  - `enforce_test_taxonomy.py`
- Structural risk detectors:
  - `check_unreachable_branches.py`
  - `check_noop_critical_paths.py`
- Reporting/export utilities:
  - `build_runtime_truth_dashboard_seed.py`
  - `build_cross_lane_dependency_map.py`
  - `export_state_transition_mermaid.py`

## Migration Rule

When adding new script suites:

1. Add a thin `run_*` entrypoint.
2. Put reusable logic in a service module/package.
3. Keep provider-specific branches explicit and testable.
4. Reuse existing shared modules before adding new helpers.
