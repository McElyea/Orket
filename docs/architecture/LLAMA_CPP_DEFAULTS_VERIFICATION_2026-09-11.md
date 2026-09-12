# llama.cpp Default Selection Verification

Date: 2026-09-11 (America/Denver).

This records the earlier default-selection baseline. The subsequent server,
template and promotion work is recorded in
[Qwen3.8 promotion verification](LLAMA_CPP_QWEN38_PROMOTION_VERIFICATION_2026-09-11.md).
The cache-workaround and pending-promotion statements below describe that earlier
baseline, not the current operator setup.

## What Changed

llama.cpp is the shared default across provider-neutral runtime, discovery,
model selection, extension catalog/generation, streaming, ODR, probes,
acceptance campaigns and proof tooling. The local model default is the exact
Qwen3.8 GGUF alias `orcarouter_qwen3.8-27b-uncensored-q4_k_l`.

Stale agent API Ollama model variables cannot select Ollama without an explicit
Ollama provider setting. Unknown providers fail before transport creation.
Missing summary evidence no longer invents an Ollama provider. Explicit provider
choices and provider-specific compatibility tests remain available. Local Ollama
was deliberately removed and is not a dependency of the llama.cpp proof path.

The installed-artifact agent acceptance runner defaults to llama.cpp, including
abrupt process recovery. See the [contract delta](CONTRACT_DELTA_LLAMA_CPP_DEFAULTS_2026-09-11.md).

## What Was Verified

- **Live, primary, success:** 10 source integration tests; 6 governed databases,
  39 model receipts, all `llama_cpp`. Default CLI/API selection, stale Ollama
  environment handling, continuation, wake/memory/replay, approval/denial across
  restart, default streaming and ODR, default extension generation/catalog,
  and provider-aware discovery passed. The extension generation used neither
  a provider nor a model override.
  [Canonical receipt](../../benchmarks/results/providers/llama_cpp_integration.json),
  [log](../../.tmp/llama-cpp-integration/proof-urzda7wq/pytest.log).
- **Live, primary, success:** 8 installed-artifact acceptance tests; 8 databases,
  54 model receipts, all `llama_cpp`. A fresh environment imported core, SDK and
  extension from its own `site-packages`, with Python isolated mode enabled.
  Both before-write and after-write process exits recovered without repeating
  the write. The acceptance command omitted `--provider` and `--model`.
  [Canonical receipt](../../benchmarks/results/governed_agent/acceptance.json),
  [log](../../.tmp/governed-agent-acceptance/execution-9wn6n1pi/pytest.log).
- **Live negative path, primary, expected failure:** a real refused connection
  remained a `provider=llama_cpp` error and never constructed an Ollama client.
- **Live, primary, success:** model listing without `--provider` returned the
  Qwen3.8 alias from `http://127.0.0.1:8080/v1`.
- **Regression:** 4,583 passed, 74 skipped, 2 warnings in 567.11 seconds.
  [Full log](../../.tmp/llama-default-proof/full-regression.log). Additional final
  focused checks: 30 passed, including the new refused-connection case, provider
  contracts, runtime package boundaries and authority-map checks.
  [Focused log](../../.tmp/llama-default-proof/final-focused.log).
- **Structural:** the clean candidate wheel matched 836 package source/resource
  files with zero mismatches and zero bundled SDK namespace entries. Installed
  versions: core candidate 0.6.1, SDK 0.6.0, external reference 0.2.0. `pip check`
  passed. This candidate differs from the tagged 0.6.1 source; it is not a new
  published release.
- **Structural:** docs project hygiene and both repositories' whitespace checks
  passed. Ruff comparison against HEAD found no added diagnostics in changed
  Python files; existing repository lint debt remains.

All live execution used `ORKET_DISABLE_SANDBOX=1`. The operator-managed server
was started hidden, with 8192 context, Jinja, reasoning off and prompt caching
disabled. No Ollama server, Docker sandbox, or alternate-provider fallback was used.

## What Was Not Verified

No new publication, formal profile promotion, distinct-model capacity, vision,
full quant campaign, production soak, or general coding-objective completion
claim is made. Compatibility-specific LM Studio/Ollama tests retain structural
coverage; live compatibility campaigns are explicit optional work, not blockers
for this default-provider change.

## Remaining Blockers or Drift

- No remaining blocker was observed for the verified llama.cpp default path.
- The current llama-server build still requires `--no-cache-prompt --cache-ram 0`.
  Cached execution and formal profile promotion remain outside this proof.
- The first candidate build picked up stale SDK files from the checkout's
  existing build cache. Verification failed visibly. Rebuilding from a clean
  source directory and reinstalling the standalone SDK last cleared that issue;
  successful installed proof uses the clean wheel. Failed attempts remain in
  the acceptance receipt's rerun history. Future builds must use clean staging.
- The bounded ticket-report verifier and separate outward approval/evidence
  findings remain as documented in the behavioral-truth review. They are not
  missing-Ollama blockers and were outside this default-selection correction.
- Changes are uncommitted; no version, tag, or release publication was performed.

## Exact Files Touched

The following inventory covers maintained source/docs/tests. Temporary build,
environment and proof artifacts are under `.tmp/llama-default-proof/` and the
canonical ignored receipt paths above. The external README had prior edits;
those were preserved while updating its default-provider instructions.

- [.env.example](../../.env.example)
- [CURRENT_AUTHORITY.md](../../CURRENT_AUTHORITY.md)
- [README.md](../../README.md)
- [docs/CONTRIBUTOR.md](../../docs/CONTRIBUTOR.md)
- [docs/RUNBOOK.md](../../docs/RUNBOOK.md)
- [docs/architecture/CONTRACT_DELTA_LLAMA_CPP_DEFAULTS_2026-09-11.md](../../docs/architecture/CONTRACT_DELTA_LLAMA_CPP_DEFAULTS_2026-09-11.md)
- [docs/architecture/LLAMA_CPP_DEFAULTS_VERIFICATION_2026-09-11.md](../../docs/architecture/LLAMA_CPP_DEFAULTS_VERIFICATION_2026-09-11.md)
- [docs/specs/APOPHENIA_EXTERNAL_EXTENSION_CONTRACT.md](../../docs/specs/APOPHENIA_EXTERNAL_EXTENSION_CONTRACT.md)
- [docs/specs/COMPANION_PROVIDER_RUNTIME_MATRIX_CONTRACT.md](../../docs/specs/COMPANION_PROVIDER_RUNTIME_MATRIX_CONTRACT.md)
- [docs/specs/GOVERNED_AGENT_LOOP_V1.md](../../docs/specs/GOVERNED_AGENT_LOOP_V1.md)
- [model/core/environments/standard.json](../../model/core/environments/standard.json)
- [orket/adapters/llm/local_model_provider.py](../../orket/adapters/llm/local_model_provider.py)
- [orket/application/services/extension_runtime_service.py](../../orket/application/services/extension_runtime_service.py)
- [orket/application/services/governed_agent_api_composition.py](../../orket/application/services/governed_agent_api_composition.py)
- [orket/discovery.py](../../orket/discovery.py)
- [orket/interfaces/routers/extension_runtime.py](../../orket/interfaces/routers/extension_runtime.py)
- [orket/orchestration/models.py](../../orket/orchestration/models.py)
- [orket/runtime/config/__init__.py](../../orket/runtime/config/__init__.py)
- [orket/runtime/config/defaults.py](../../orket/runtime/config/defaults.py)
- [orket/runtime/config/local_prompt_profiles.py](../../orket/runtime/config/local_prompt_profiles.py)
- [orket/runtime/config/provider_discovery.py](../../orket/runtime/config/provider_discovery.py)
- [orket/runtime/config/provider_runtime_target.py](../../orket/runtime/config/provider_runtime_target.py)
- [orket/runtime/execution/execution_pipeline_run_summary.py](../../orket/runtime/execution/execution_pipeline_run_summary.py)
- [orket/runtime/policy/safe_default_catalog.py](../../orket/runtime/policy/safe_default_catalog.py)
- [orket/runtime/summary/run_summary.py](../../orket/runtime/summary/run_summary.py)
- [orket/workloads/model_stream_v1.py](../../orket/workloads/model_stream_v1.py)
- [scripts/acceptance/run_architecture_pilot_matrix.py](../../scripts/acceptance/run_architecture_pilot_matrix.py)
- [scripts/acceptance/run_microservices_unlock_evidence.py](../../scripts/acceptance/run_microservices_unlock_evidence.py)
- [scripts/acceptance/run_monolith_variant_matrix.py](../../scripts/acceptance/run_monolith_variant_matrix.py)
- [scripts/benchmarks/run_local_model_coding_challenge.py](../../scripts/benchmarks/run_local_model_coding_challenge.py)
- [scripts/companion/run_companion_provider_runtime_matrix.py](../../scripts/companion/run_companion_provider_runtime_matrix.py)
- [scripts/companion/run_companion_provider_runtime_matrix_pipeline.py](../../scripts/companion/run_companion_provider_runtime_matrix_pipeline.py)
- [scripts/extensions/play_lie_detector.py](../../scripts/extensions/play_lie_detector.py)
- [scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py](../../scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py)
- [scripts/governance/record_truthful_runtime_packet1_live_proof.py](../../scripts/governance/record_truthful_runtime_packet1_live_proof.py)
- [scripts/governance/record_truthful_runtime_packet2_repair_live_proof.py](../../scripts/governance/record_truthful_runtime_packet2_repair_live_proof.py)
- [scripts/odr/run_odr_7b_baseline.py](../../scripts/odr/run_odr_7b_baseline.py)
- [scripts/odr/run_odr_live_role_matrix.py](../../scripts/odr/run_odr_live_role_matrix.py)
- [scripts/odr/run_odr_role_matrix.py](../../scripts/odr/run_odr_role_matrix.py)
- [scripts/odr/run_odr_single_vs_coordinated.py](../../scripts/odr/run_odr_single_vs_coordinated.py)
- [scripts/probes/p01_single_issue.py](../../scripts/probes/p01_single_issue.py)
- [scripts/probes/p02_odr_isolation.py](../../scripts/probes/p02_odr_isolation.py)
- [scripts/probes/p03_epic_trace.py](../../scripts/probes/p03_epic_trace.py)
- [scripts/probes/p04_odr_cards_integration.py](../../scripts/probes/p04_odr_cards_integration.py)
- [scripts/probes/probe_support.py](../../scripts/probes/probe_support.py)
- [scripts/proof/run_governed_agent_acceptance.py](../../scripts/proof/run_governed_agent_acceptance.py)
- [scripts/proof/run_outward_write_file_approved_proof.py](../../scripts/proof/run_outward_write_file_approved_proof.py)
- [scripts/providers/check_model_provider_preflight.py](../../scripts/providers/check_model_provider_preflight.py)
- [scripts/providers/provider_model_resolver.py](../../scripts/providers/provider_model_resolver.py)
- [scripts/streaming/provider_identity.py](../../scripts/streaming/provider_identity.py)
- [scripts/workloads/code_review_probe.py](../../scripts/workloads/code_review_probe.py)
- [scripts/workloads/decompose_and_route.py](../../scripts/workloads/decompose_and_route.py)
- [scripts/workloads/generate_and_verify.py](../../scripts/workloads/generate_and_verify.py)
- [tests/adapters/test_local_model_provider_telemetry.py](../../tests/adapters/test_local_model_provider_telemetry.py)
- [tests/application/test_discovery_engine_recommendations.py](../../tests/application/test_discovery_engine_recommendations.py)
- [tests/e2e/test_governed_agent_llama_cpp.py](../../tests/e2e/test_governed_agent_llama_cpp.py)
- [tests/e2e/test_governed_agent_process_recovery.py](../../tests/e2e/test_governed_agent_process_recovery.py)
- [tests/live/test_llama_cpp_feature_paths.py](../../tests/live/test_llama_cpp_feature_paths.py)
- [tests/runtime/test_local_provider_defaults.py](../../tests/runtime/test_local_provider_defaults.py)
- [tests/runtime/test_run_summary_packet1.py](../../tests/runtime/test_run_summary_packet1.py)
- External: [GoverenedAgentLoop/README.md](../../../OrketExtensions/GoverenedAgentLoop/README.md)
