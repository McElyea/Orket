# llama.cpp Feature Integration Verification

Date: 2026-09-10 (America/Denver).

## Changes

Governed-agent CLI/API/wake/resume paths now use common local-provider composition.
Streaming admission and evidence, model listing, quant wrapper selection, ODR
endpoints, and the exact Qwen3.8 prompt profile include llama.cpp. API startup
initializes the wake store before ingress and the supervisor can race SQLite WAL.
See [the contract delta](CONTRACT_DELTA_LLAMA_CPP_FEATURE_INTEGRATION_2026-09-10.md)
for boundaries and migration.

## Verification

- Live, primary, success: 9 integration tests; 6 durable governed-run databases;
  39 model receipts, all identifying llama_cpp and
  orcarouter_qwen3.8-27b-uncensored-q4_k_l. Covers default/explicit CLI selection,
  staged continuation, API wake, memory, replay, effect approval/denial across
  restart, streaming through commit, and both ODR role-endpoint paths.
- Canonical receipt: [llama_cpp_integration.json](../../benchmarks/results/providers/llama_cpp_integration.json).
  It retains rerun diff history and references per-run logs and SQLite evidence.
- Live standalone streaming gate: six scenarios passed, including provider
  preflight, token delivery, cancellation and the existing cold-load visibility
  scenario. The latter proves visibility with an already operator-loaded model,
  not that Orket loaded a cold model. Gate id: gate-70d5d8982cd2.
- Live Qwen3.8 conformance smoke: JSON 3/3, JSON-wrapper tool calls 3/3, no
  protocol chatter or markdown fences. Evidence under
  [the conformance directory](../../.tmp/qwen38-llamacpp/conformance).
- Live model-list query selected llama_cpp at port 8080. Quant wrapper dry run
  resolved the exact served model; this is selection/wiring proof only.
- Full regression suite: 4574 passed, 73 skipped, 2 warnings, 563.13 seconds.
  This run preceded the final startup ordering and identity hardening edits.
- Final interface/provider/streaming regression run: 463 passed in 86.58 seconds.
  It includes the API startup fix and exact provider identity checks. Final
  authority/provider contracts after the last helper-parameter rename: 25 passed.
- Docs project hygiene, authority-map checks, whitespace checks, and focused
  Ruff checks passed. Deterministic and mocked contracts are structural proof;
  they are not counted as live provider evidence.

## Not Verified

No new installed release or package publication was performed. LM Studio and
Ollama retain deterministic regression coverage; they were not rerun live in
this change. Distinct-model llama.cpp capacity, vision, full quant sweeps, model
quality comparisons, production soak, and formal profile promotion are unproven.
Promotion still requires 1000 JSON cases, 500 tool cases, and template-audit gates.

## Remaining Blockers or Drift

- The local llama-server build dd7cad7 aborted while reusing recurrent prompt
  cache state. The final server and successful proof use
  `--no-cache-prompt --cache-ram 0`, an 8192-token context, Jinja and reasoning off.
  Upstream cached execution remains unverified. The failure and subsequent
  successful reruns remain in the receipt history and local logs.
- SQLite startup contention was reproduced during focused API tests and fixed
  by awaiting wake-store initialization before serving requests. The regression
  now checks WAL before scheduled ingress; the final interface and live API
  runs pass.
- The local prompt audit remains message-payload-audited. Captured server
  template SHA256 is c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041;
  metadata capture alone is not a formal template-integrity audit.
- Existing unrelated architecture exceptions remain outside this change. A
  pre-existing unused local variable in the ODR comparison script remains;
  focused lint is not a repo-wide lint-clean claim.
- Published core 0.6.0 artifacts predate this source integration. Changes are
  uncommitted; no versions, tags, or release assets were changed.

## Exact Files Touched

The inventory includes the provider-preference documentation edits already in
this worktree when implementation began. The unrelated untracked gardener HTML
brief was preserved.

- [CURRENT_AUTHORITY.md](../../CURRENT_AUTHORITY.md)
- [docs/CONTRIBUTOR.md](../../docs/CONTRIBUTOR.md)
- [docs/RUNBOOK.md](../../docs/RUNBOOK.md)
- [docs/architecture/CONTRACT_DELTA_LLAMA_CPP_FEATURE_INTEGRATION_2026-09-10.md](../../docs/architecture/CONTRACT_DELTA_LLAMA_CPP_FEATURE_INTEGRATION_2026-09-10.md)
- [docs/architecture/LLAMA_CPP_FEATURE_INTEGRATION_VERIFICATION_2026-09-10.md](../../docs/architecture/LLAMA_CPP_FEATURE_INTEGRATION_VERIFICATION_2026-09-10.md)
- [docs/specs/GOVERNED_AGENT_LOOP_V1.md](../../docs/specs/GOVERNED_AGENT_LOOP_V1.md)
- [docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md](../../docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md)
- Removed: orket/adapters/llm/governed_agent_ollama_provider.py
- [orket/adapters/llm/local_model_provider.py](../../orket/adapters/llm/local_model_provider.py)
- [orket/adapters/llm/local_model_provider_runtime_target.py](../../orket/adapters/llm/local_model_provider_runtime_target.py)
- [orket/application/services/governed_agent_api_composition.py](../../orket/application/services/governed_agent_api_composition.py)
- [orket/application/services/governed_agent_execution_composition.py](../../orket/application/services/governed_agent_execution_composition.py)
- [orket/application/services/governed_agent_model_provider.py](../../orket/application/services/governed_agent_model_provider.py)
- [orket/application/services/governed_agent_runtime.py](../../orket/application/services/governed_agent_runtime.py)
- [orket/application/services/governed_agent_wake_dispatcher.py](../../orket/application/services/governed_agent_wake_dispatcher.py)
- [orket/interfaces/api.py](../../orket/interfaces/api.py)
- [orket/interfaces/governed_agent_cli.py](../../orket/interfaces/governed_agent_cli.py)
- [orket/runtime/config/local_prompt_profiles.json](../../orket/runtime/config/local_prompt_profiles.json)
- [orket/runtime/config/provider_truth_table.py](../../orket/runtime/config/provider_truth_table.py)
- [orket/streaming/model_provider.py](../../orket/streaming/model_provider.py)
- [orket/workloads/model_stream_v1.py](../../orket/workloads/model_stream_v1.py)
- [scripts/odr/model_runtime_control.py](../../scripts/odr/model_runtime_control.py)
- [scripts/odr/run_odr_7b_baseline.py](../../scripts/odr/run_odr_7b_baseline.py)
- [scripts/odr/run_odr_single_vs_coordinated.py](../../scripts/odr/run_odr_single_vs_coordinated.py)
- [scripts/proof/run_llama_cpp_integration.py](../../scripts/proof/run_llama_cpp_integration.py)
- [scripts/providers/list_real_provider_models.py](../../scripts/providers/list_real_provider_models.py)
- [scripts/quant/tune_quant_sweep_provider_ready.py](../../scripts/quant/tune_quant_sweep_provider_ready.py)
- [scripts/streaming/provider_identity.py](../../scripts/streaming/provider_identity.py)
- [scripts/streaming/run_live_1000_consistency.py](../../scripts/streaming/run_live_1000_consistency.py)
- [scripts/streaming/run_model_streaming_gate.py](../../scripts/streaming/run_model_streaming_gate.py)
- [scripts/streaming/run_provider_scenario_direct.py](../../scripts/streaming/run_provider_scenario_direct.py)
- [scripts/streaming/run_stream_scenario.py](../../scripts/streaming/run_stream_scenario.py)
- [tests/adapters/test_governed_agent_ollama_provider.py](../../tests/adapters/test_governed_agent_ollama_provider.py)
- [tests/application/test_governed_agent_local_provider.py](../../tests/application/test_governed_agent_local_provider.py)
- [tests/e2e/test_governed_agent_effect_ollama.py](../../tests/e2e/test_governed_agent_effect_ollama.py)
- [tests/e2e/test_governed_agent_llama_cpp.py](../../tests/e2e/test_governed_agent_llama_cpp.py)
- [tests/e2e/test_governed_agent_ollama.py](../../tests/e2e/test_governed_agent_ollama.py)
- [tests/e2e/test_governed_agent_supervisor_ollama.py](../../tests/e2e/test_governed_agent_supervisor_ollama.py)
- [tests/interfaces/test_governed_agent_api.py](../../tests/interfaces/test_governed_agent_api.py)
- [tests/live/test_llama_cpp_feature_paths.py](../../tests/live/test_llama_cpp_feature_paths.py)
- [tests/scripts/test_stream_provider_identity.py](../../tests/scripts/test_stream_provider_identity.py)
- [tests/streaming/test_stream_test_workload.py](../../tests/streaming/test_stream_test_workload.py)
- External: [GoverenedAgentLoop/README.md](../../../OrketExtensions/GoverenedAgentLoop/README.md)
