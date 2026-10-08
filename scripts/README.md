# Scripts Organization

This folder contains command entrypoints and shared script modules.

The bounded authority index is authored in `docs/architecture/current_authority.json`.
Generate its view with `python scripts/governance/render_current_authority.py`;
`--check` compares without writing. Validate sources and generated equality with
`python scripts/governance/check_current_authority.py`. The stable report is
`benchmarks/results/governance/current_authority_check.json`, with the shared diff
ledger. A structural pass grants no current execution proof; `--require-current-proof`
refuses while runtime receipt adapters remain unavailable. Source contract:
`docs/specs/CURRENT_AUTHORITY_SOURCE_CONTRACT.md`.

## Layout

`python scripts/ci/verify_candidate_install.py` builds and checks core/SDK wheels
from fresh Git-visible inputs in an external isolated environment. Its stable
reports are `.tmp/macos-support/package-install.json` and
`.tmp/macos-support/package-inputs.json`, with rerun diff ledgers. Candidate
wheels, per-command logs and example projects are retained under the external
directory named in the report. `--require-macos-arm64` requires native Darwin
arm64 and does not bypass unavailable command ownership. Instructions and proof
limits: `docs/guides/MACOS_LOCAL_INSTALL.md`. A passing packaging slice is not
full Mac acceptance or live provider proof.

`python scripts/ci/verify_installed_process_acceptance.py` consumes that verified
candidate and runs the existing native process controls outside the checkout.
The stable result is `.tmp/macos-support/process-acceptance.json`; its retained
external directory contains copied test sources, JUnit evidence, logs and fixture
state. It checks all mandatory items and refuses skips. `--windows-control`
explicitly proves only Windows behavior. The same core wheel's declared dev extra
supplies test tooling; installation, imports and the final dependency set are
recorded. Full native Mac/provider/Metal acceptance remains separate.

`python scripts/ci/verify_macos_acceptance.py --llama-server <absolute-executable> --model-file <absolute-gguf>`
combines those components with guided setup and actual llama.cpp workflow/restart
proof. Stable `.tmp/macos-support/native-acceptance.json` records every required
MA case and owned server/Metal observations. Windows control reports partial
success only; missing Metal or mandatory native cases cannot grant Mac acceptance.
Preparation, evidence retrieval and teardown: `docs/guides/MACOS_ACCEPTANCE_RUNBOOK.md`.

The live card and collection suite commands now share
`scripts/benchmarks/live_suite.py`: both default to the executable 80-task v2 bank,
accept `--model` and optional ID bounds, and fail on failed/missing workload runs.
`--require-score` additionally enforces the unchanged scoring report. Their stable
staging outputs are `benchmarks/staging/General/live_{card,rock}_suite.json` and
`live_{card,rock}_suite_scored.json`, with rerun diff ledgers. The v1 bank remains
fixture/control metadata; it is not the live default. Details and proof limits:
`docs/specs/WORKFLOW_BENCHMARK_READINESS.md`.

The canonical coverage configuration writes measurements under `.tmp/quality/`,
matching `.gitea/workflows/quality.yml`. Root `.coverage` is historical data and
must not be used as current proof. See `docs/CONTRIBUTOR.md` for the unchanged gate.

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

## Benchmark process invocation

Readiness and outcome rules: `docs/specs/WORKFLOW_BENCHMARK_READINESS.md`.
Run `python scripts/governance/check_workflow_preflight.py --project <project>
--epic <name>` before inference; the report is structural, not completion proof.
The live benchmark runners retain one isolated project/board per invocation and
require explicit function examples or CLI examples with a retained implementation
inventory and exact stdout/stderr/exit expectations. Undefined shapes still refuse.
The v2 CLI bank uses the corrected 0.7.6 expectations; compare its historical
results only with that input change disclosed. Prepared `standard`,
`qa_completion_test` and bounded `sanity_test` recipes are documented in
`examples/stored_workflows/README.md`.

The service load harness follows `--epic-id <real-target>` to accepted completion;
without that option it tests missing-target refusal. Its stable default output is
`benchmarks/staging/General/service_load.json`. The real-service stress launcher
defaults to API 8082 and webhook 8083 and honors both port options.
`python scripts/streaming/diagnose_llama_stream.py --model <selected-alias>` records
idle-slot checks and first-token timing without changing the model or timeouts.
`python scripts/reviewrun/run_30page_consistency.py --runs 1000` retains a hashed
Git bundle and verifies a deterministic baseline. Use `--policy <path>` to reuse
a retained policy and `--historical-report <path>` to recover exact commits from
surviving objects without modifying the original fixture. Use `--expected-decision`
to refuse consistent but semantically wrong results.

The live card and collection benchmark suites launch repository-owned Python
children with the invoking interpreter (`sys.executable`), including generated
program checks. The determinism harness parses runner templates using native
Windows argv rules on Windows, preserving quoted executable paths and arguments;
it invokes the resulting argv without a shell. Explicit operator runner templates
retain their selected executable. A successful harness or scoring command alone
does not establish successful model work; inspect individual outcomes and evidence.

The API streaming scenario runner enters the real API lifespan before sending
session or WebSocket requests and exits it after the scenario traffic settles.
Its three baseline scenarios use deterministic workloads; provider scenarios in
the real-mode gate call the selected model. A passing single loop does not prove
the 1,000-loop endurance gate completed.

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
  - `check_narration_effect_audit_policy.py`
  - `check_source_attribution_policy.py`
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
  - `check_spec_debt_queue.py`
  - `check_non_fatal_error_budget.py`
  - `check_interface_freeze_windows.py`
  - `check_evidence_package_generator_contract.py`
  - `check_observability_redaction_tests.py`
  - `check_trust_language_review.py`
  - `check_local_remote_route_policy.py`
  - `check_failure_replay_harness_contract.py`
  - `check_cold_start_truth_tests.py`
  - `check_persistence_corruption_test_suite.py`
  - `check_long_session_soak_tests.py`
  - `check_resource_pressure_simulation_lane.py`
  - `check_ui_lane_security_boundary_tests.py`
  - `check_degradation_first_ui_standard.py`
  - `check_decision_record_operating_principles_contract.py`
  - `check_naming_discipline_policy.py`
  - `check_promotion_rollback_criteria.py`
  - `check_environment_parity_checklist.py`
  - `check_runtime_config_ownership_map.py`
  - `check_runtime_invariant_registry.py`
  - `check_runtime_boundary_audit_checklist.py`
  - `check_provider_quarantine_policy.py`
  - `check_unknown_input_policy.py`
  - `check_safe_default_catalog.py`
  - `check_clock_time_authority_policy.py`
  - `check_capability_fallback_hierarchy.py`
  - `check_runtime_truth_foundation_contracts.py`
  - `check_retry_classification_policy.py`
  - `check_result_error_invariants.py`
  - `check_structured_warning_policy.py`
  - `enforce_test_taxonomy.py`
- Structural risk detectors:
  - `check_unreachable_branches.py`
  - `check_noop_critical_paths.py`
- Reporting/export utilities:
  - `build_runtime_truth_dashboard_seed.py`
  - `build_cross_lane_dependency_map.py`
  - `export_state_transition_mermaid.py`
  - `generate_runtime_truth_evidence_package.py`
  - `run_failure_replay_harness.py`

## Migration Rule

When adding new script suites:

1. Add a thin `run_*` entrypoint.
2. Put reusable logic in a service module/package.
3. Keep provider-specific branches explicit and testable.
4. Reuse existing shared modules before adding new helpers.
