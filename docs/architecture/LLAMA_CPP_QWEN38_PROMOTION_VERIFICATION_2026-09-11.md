# llama.cpp Qwen3.8 Promotion Verification

Date: 2026-09-11 (America/Denver). Decision: promoted for the exact bounded profile below.

Release follow-up: [core 0.6.2](../releases/0.6.2/PROOF_REPORT.md) binds these
changes to a versioned release and records fresh installed-artifact acceptance.
The candidate versions and publication status below describe this earlier proof.

## What Changed

The operator server is now upstream llama.cpp `b10809-5266f24da`, using CUDA on
the RTX 4090 with one slot, an 8192-token context and prompt caching enabled.
The old `dd7cad7` binary is retained for rollback investigation. The new server
uses the packaged 230-byte text ChatML template. No Ollama server or provider
fallback is involved.

The adapter verifies server template/model identity and native rendered prompts
before generation, uses shared LP-02 canonicalization, and measures native input
tokens before enforcing the input/output context limit. The profile keeps
JSON-wrapper tools and reasoning suppression. Tool-history text is preserved.

Promotion tools now reject absent template bytes, unapproved branches, wrong tool
names/arguments and incomplete reruns. Whitelist records bind template hashes to
reviewers and approval references. Every final corpus case retains its output,
render hash, template identity and native token-count source. Corrective prompts
retain stable failure details and prior-output hashes. Empty continuation replay
reports `no_decisions` instead of a successful match.

Authority: [contract delta](CONTRACT_DELTA_QWEN38_PROMOTION_2026-09-11.md),
[operator command](../RUNBOOK.md#governed-agent-bounded-cli).

## What Was Verified

All inference proof uses `ORKET_DISABLE_SANDBOX=1`, the primary llama.cpp path,
and the exact alias `orcarouter_qwen3.8-27b-uncensored-q4_k_l`.

- Model SHA256: `431c4818df8a3ce941e2fe35bc37688ea9c30052339eae8f41a4c25cdd9a6fa7`.
- Both downloaded Windows CUDA archives match the digests supplied by the
  [official upstream b10809 release](https://github.com/ggml-org/llama.cpp/releases/tag/b10809).
  The 57 installed files and archive hashes are recorded in the
  [server installation manifest](../../benchmarks/results/protocol/local_prompting/qwen38_promotion/server_installation.json).
- Active template SHA256: `8fc57a9f65eaaaee48e80771aea4775f7d3a8adb466a6193d8de551fa124d578`.
- Inactive tokenizer template SHA256: `c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041`.
  Its content-sensitive branches were rejected; no whitelist exception was used.
  The active override passed its own byte-backed audit.
- **Live, primary, success:** repeated-prefix cache reuse, changed histories,
  cancellation followed by recovery, per-class stop/sampling settings, all-role
  history and native-token over-budget refusal. Evidence:
  [runtime readiness](../../benchmarks/results/protocol/local_prompting/qwen38_promotion/runtime_readiness.json).
  Repeated long prefixes reused 533 tokens; changed histories reused 21 tokens
  and returned the correct requested values. Both structured must-stop cases
  terminated on their sentinel while the corresponding sentinel-free request
  reached the 64-token limit. Native tokenizer counts matched provider-reported
  input usage in all five successful supplemental adapter cases.
- **Live, primary, success:** deliberately induced markdown fencing was rejected
  by the shared host validator and corrected by the real model after one bounded
  reprompt. Evidence:
  [repair readiness](../../benchmarks/results/protocol/local_prompting/qwen38_promotion/repair_readiness.json).
- **Live, primary, success:** 10 source integration tests cover agent CLI/API,
  memory, replay, approved/denied effects, streaming, ODR, extension generation
  and discovery. Evidence:
  [source integration](../../benchmarks/results/providers/llama_cpp_integration.json).
- **Live, primary, success:** 8 installed-package tests cover the same bounded
  agent path and abrupt process exits immediately before/after a real write.
  Recovery does not repeat the write. Core, SDK and extension imports resolve
  inside the isolated environment. Evidence:
  [installed acceptance](../../benchmarks/results/governed_agent/acceptance.json).
- **Structural, success:** the final wheel matches 840 source/resource files,
  has zero SDK namespace entries, and passes `pip check`. Core candidate 0.6.1,
  SDK 0.6.0, external reference 0.2.0. Evidence:
  [package identity](../../benchmarks/results/protocol/local_prompting/qwen38_promotion/package_identity.json).
- **Regression:** 4,609 passed, 74 skipped, 2 warnings in 488.38 seconds on the
  final runtime code. The final audit/gate/authority checks additionally passed
  38 tests, including the clean-template scanner boundary regression added
  after full-suite collection.
  [Full log](../../.tmp/qwen38-full-regression-final.log),
  [gate log](../../.tmp/qwen38-final-gate-tests.log).
- **Live, primary, success:** final corpus passed 1000/1000 JSON and 500/500
  exact tool cases, with zero markdown fences or protocol chatter. All 1500
  native token counts matched reported input usage; all render checks passed.
  The strict readiness command exited zero with every profile/drift gate green.
  [Final corpus log](../../.tmp/qwen38-promotion-final.log),
  [promotion decision](../../benchmarks/results/protocol/local_prompting/qwen38_promotion/promotion_readiness.json),
  [closeout manifest](../../benchmarks/results/protocol/local_prompting/qwen38_promotion/promotion_closeout.json).
- **Structural, success:** semantic profile drift is zero against the frozen
  candidate baseline; the intentional old-to-new template delta is retained.
  In-progress rerun rejection was also observed using the real retained reports.
- **Structural, success:** docs hygiene, authority checks and whitespace checks
  pass. No added Ruff diagnostics remain; pre-existing repository lint debt is
  not represented as a clean repository-wide lint result.

The first corpus run passed 1000/1000 JSON and 500/500 tool cases. A complete
second run verifies the final shared canonicalization and native-token telemetry;
the first run is retained as history, not substituted for final implementation
proof. The PowerShell wrapper of the first run returned nonzero on stderr
warnings despite green corpus reports; the final wrapper records Python's exit
status explicitly.

## LP-01 Through LP-16 Evidence Map

| Requirements | Evidence and limits |
| --- | --- |
| LP-01 profile resolution | Exact alias/profile in corpus, runtime receipts, and profile contract tests. |
| LP-02 hashing | Every final corpus request compares native/reference bytes, then uses shared canonical LF/per-line trailing-space normalization. |
| LP-03 roles | Live system/user/assistant/tool history; unsupported role and non-text contract refusals. |
| LP-04 stopping | Per-class live stops, explicit JSON/tool sentinels, and bounded repeated-output counterfactuals. |
| LP-05 schemas | 1000 exact JSON objects and 500 exact tool/argument objects; wrong-tool/argument negative tests. |
| LP-06 prefill | `prefill_strategy=none`; live repair and host retry-budget tests cover the stricter path. |
| LP-07 context | Native `/tokenize`, profile/server minimum budget, output reservation, real oversized-input refusal; deterministic history reduction retained. |
| LP-08 sampling | Bounded outputs and server-reported effective values for four task classes; no output-distribution claim. |
| LP-09 repair | Real induced failure/one-repair convergence; structural terminal-retry tests and real-child/durable-budget integration tests. |
| LP-10 anti-meta | Corpus payload-only validation, live fenced-output rejection, strict thinking suppression, denylist/whitespace contract tests. |
| LP-11 observability | Runtime metadata and final per-case render/template/native-token receipts, with exact model/profile identity. |
| LP-12 matrix | This exact llama.cpp model/profile and its supported feature routes; other models/providers are not newly promoted. |
| LP-13 upgrade drift | Recorded original-to-candidate profile delta plus frozen candidate-to-final comparison and rerun metric history. |
| LP-14 fallback | Exact target admission and unknown-profile refusal; retained real refused-connection proof never creates an alternate-provider client. |
| LP-15 rendering | Native `/apply-template` compared with independent text renderer before generation, plus mismatch contract tests. |
| LP-16 template audit | Actual original and override bytes audited; original rejected/inactive, override clean and hash-bound to render/profile evidence. |

## What Was Not Verified

No new release was published. The installed wheel is an uncommitted source
candidate based on tagged core 0.6.1, not the original 0.6.1 release artifact.
No distinct-model capacity, production soak, vision, native tool-calling or full
quant campaign is claimed. Effective sampling values are server-reported;
statistical sampling distributions are not measured. Loaded weight digests are
observed independently and are not cryptographic attestations in model receipts.

The governed-agent reference verifier remains the explicitly admitted ticket
report verifier. This work does not supply arbitrary coding-objective verification
or hostile-extension containment. Repair terminal-budget proof includes controlled
provider fixtures; it is not represented as live model nonconvergence proof.

## Remaining Blockers or Drift

No remaining blocker was observed for this exact provider/profile and the
documented bounded agent loop. Broader architectural-truth work remains on its
own roadmap lane. This report does not retire that initiative.

## Exact Files Touched

The combined uncommitted default-selection and promotion candidate touches the
following repository files: Temporary logs, proof artifacts and the isolated
candidate environment remain under `.tmp/` and `benchmarks/results/`. The operator
installation is under `D:/llama.cpp-releases/b10809/`; the existing model weights
and old source checkout were not edited.

- [.env.example](../../.env.example)
- [CURRENT_AUTHORITY.md](../../CURRENT_AUTHORITY.md)
- [README.md](../../README.md)
- [docs/CONTRIBUTOR.md](../../docs/CONTRIBUTOR.md)
- [docs/ROADMAP.md](../../docs/ROADMAP.md)
- [docs/RUNBOOK.md](../../docs/RUNBOOK.md)
- [docs/architecture/CONTRACT_DELTA_LLAMA_CPP_DEFAULTS_2026-09-11.md](../../docs/architecture/CONTRACT_DELTA_LLAMA_CPP_DEFAULTS_2026-09-11.md)
- [docs/architecture/CONTRACT_DELTA_QWEN38_PROMOTION_2026-09-11.md](../../docs/architecture/CONTRACT_DELTA_QWEN38_PROMOTION_2026-09-11.md)
- [docs/architecture/LLAMA_CPP_DEFAULTS_VERIFICATION_2026-09-11.md](../../docs/architecture/LLAMA_CPP_DEFAULTS_VERIFICATION_2026-09-11.md)
- [docs/architecture/LLAMA_CPP_QWEN38_PROMOTION_VERIFICATION_2026-09-11.md](../../docs/architecture/LLAMA_CPP_QWEN38_PROMOTION_VERIFICATION_2026-09-11.md)
- [docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md](../../docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md)
- [docs/projects/architectural-truth/BEHAVIORAL_TRUTH_ARCHITECTURE_REVIEW_2026-09-10.md](../../docs/projects/architectural-truth/BEHAVIORAL_TRUTH_ARCHITECTURE_REVIEW_2026-09-10.md)
- [docs/projects/architectural-truth/README.md](../../docs/projects/architectural-truth/README.md)
- [docs/projects/archive/local-provider-promotion/2026-09-11-QWEN38-PROMOTION/LLAMA_CPP_QWEN38_PROMOTION_PLAN.md](../../docs/projects/archive/local-provider-promotion/2026-09-11-QWEN38-PROMOTION/LLAMA_CPP_QWEN38_PROMOTION_PLAN.md)
- [docs/specs/APOPHENIA_EXTERNAL_EXTENSION_CONTRACT.md](../../docs/specs/APOPHENIA_EXTERNAL_EXTENSION_CONTRACT.md)
- [docs/specs/COMPANION_PROVIDER_RUNTIME_MATRIX_CONTRACT.md](../../docs/specs/COMPANION_PROVIDER_RUNTIME_MATRIX_CONTRACT.md)
- [docs/specs/GOVERNED_AGENT_LOOP_V1.md](../../docs/specs/GOVERNED_AGENT_LOOP_V1.md)
- [docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md](../../docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md)
- [model/core/environments/standard.json](../../model/core/environments/standard.json)
- [orket/adapters/llm/llama_cpp_render_verification.py](../../orket/adapters/llm/llama_cpp_render_verification.py)
- [orket/adapters/llm/local_model_provider.py](../../orket/adapters/llm/local_model_provider.py)
- [orket/adapters/llm/local_prompting_policy.py](../../orket/adapters/llm/local_prompting_policy.py)
- [orket/adapters/llm/prompt_canonicalization.py](../../orket/adapters/llm/prompt_canonicalization.py)
- [orket/application/services/extension_runtime_service.py](../../orket/application/services/extension_runtime_service.py)
- [orket/application/services/governed_agent_api_composition.py](../../orket/application/services/governed_agent_api_composition.py)
- [orket/application/services/governed_agent_inspection_service.py](../../orket/application/services/governed_agent_inspection_service.py)
- [orket/application/workflows/turn_corrective_prompt.py](../../orket/application/workflows/turn_corrective_prompt.py)
- [orket/discovery.py](../../orket/discovery.py)
- [orket/interfaces/routers/extension_runtime.py](../../orket/interfaces/routers/extension_runtime.py)
- [orket/orchestration/models.py](../../orket/orchestration/models.py)
- [orket/runtime/config/__init__.py](../../orket/runtime/config/__init__.py)
- [orket/runtime/config/defaults.py](../../orket/runtime/config/defaults.py)
- [orket/runtime/config/local_prompt_profiles.json](../../orket/runtime/config/local_prompt_profiles.json)
- [orket/runtime/config/local_prompt_profiles.py](../../orket/runtime/config/local_prompt_profiles.py)
- [orket/runtime/config/provider_discovery.py](../../orket/runtime/config/provider_discovery.py)
- [orket/runtime/config/provider_runtime_target.py](../../orket/runtime/config/provider_runtime_target.py)
- [orket/runtime/config/qwen38_text_chatml.jinja](../../orket/runtime/config/qwen38_text_chatml.jinja)
- [orket/runtime/execution/execution_pipeline_run_summary.py](../../orket/runtime/execution/execution_pipeline_run_summary.py)
- [orket/runtime/policy/safe_default_catalog.py](../../orket/runtime/policy/safe_default_catalog.py)
- [orket/runtime/summary/run_summary.py](../../orket/runtime/summary/run_summary.py)
- [orket/workloads/model_stream_v1.py](../../orket/workloads/model_stream_v1.py)
- [pyproject.toml](../../pyproject.toml)
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
- [scripts/proof/run_qwen38_repair_readiness.py](../../scripts/proof/run_qwen38_repair_readiness.py)
- [scripts/proof/run_qwen38_runtime_readiness.py](../../scripts/proof/run_qwen38_runtime_readiness.py)
- [scripts/protocol/audit_prompt_templates.py](../../scripts/protocol/audit_prompt_templates.py)
- [scripts/protocol/check_local_prompting_promotion_readiness.py](../../scripts/protocol/check_local_prompting_promotion_readiness.py)
- [scripts/protocol/local_prompting_conformance_helpers.py](../../scripts/protocol/local_prompting_conformance_helpers.py)
- [scripts/protocol/local_prompting_conformance_runner.py](../../scripts/protocol/local_prompting_conformance_runner.py)
- [scripts/protocol/local_prompting_render_evidence.py](../../scripts/protocol/local_prompting_render_evidence.py)
- [scripts/protocol/local_prompting_template_gate.py](../../scripts/protocol/local_prompting_template_gate.py)
- [scripts/protocol/run_local_prompting_conformance.py](../../scripts/protocol/run_local_prompting_conformance.py)
- [scripts/providers/check_model_provider_preflight.py](../../scripts/providers/check_model_provider_preflight.py)
- [scripts/providers/provider_model_resolver.py](../../scripts/providers/provider_model_resolver.py)
- [scripts/streaming/provider_identity.py](../../scripts/streaming/provider_identity.py)
- [scripts/workloads/code_review_probe.py](../../scripts/workloads/code_review_probe.py)
- [scripts/workloads/decompose_and_route.py](../../scripts/workloads/decompose_and_route.py)
- [scripts/workloads/generate_and_verify.py](../../scripts/workloads/generate_and_verify.py)
- [tests/adapters/test_llama_cpp_render_verification.py](../../tests/adapters/test_llama_cpp_render_verification.py)
- [tests/adapters/test_local_model_provider_telemetry.py](../../tests/adapters/test_local_model_provider_telemetry.py)
- [tests/application/test_discovery_engine_recommendations.py](../../tests/application/test_discovery_engine_recommendations.py)
- [tests/application/test_turn_corrective_prompt.py](../../tests/application/test_turn_corrective_prompt.py)
- [tests/e2e/test_governed_agent_llama_cpp.py](../../tests/e2e/test_governed_agent_llama_cpp.py)
- [tests/e2e/test_governed_agent_process_recovery.py](../../tests/e2e/test_governed_agent_process_recovery.py)
- [tests/integration/test_governed_agent_empty_replay.py](../../tests/integration/test_governed_agent_empty_replay.py)
- [tests/integration/test_packaged_local_prompt_registry.py](../../tests/integration/test_packaged_local_prompt_registry.py)
- [tests/live/test_llama_cpp_feature_paths.py](../../tests/live/test_llama_cpp_feature_paths.py)
- [tests/runtime/test_local_provider_defaults.py](../../tests/runtime/test_local_provider_defaults.py)
- [tests/runtime/test_run_summary_packet1.py](../../tests/runtime/test_run_summary_packet1.py)
- [tests/scripts/test_audit_prompt_templates.py](../../tests/scripts/test_audit_prompt_templates.py)
- [tests/scripts/test_check_local_prompting_promotion_readiness.py](../../tests/scripts/test_check_local_prompting_promotion_readiness.py)
- [tests/scripts/test_local_prompting_template_gate.py](../../tests/scripts/test_local_prompting_template_gate.py)

External repository: [GoverenedAgentLoop README](../../../OrketExtensions/GoverenedAgentLoop/README.md).
