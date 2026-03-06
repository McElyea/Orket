# Protocol-Governed Local Prompting Plan (v1.1)

Last updated: 2026-03-06  
Status: Active (Execution Complete; Monitor)  
Owner: Orket Core

References:
1. `docs/projects/protocol-governed/local-prompting-requirements.md`
2. `docs/projects/protocol-governed/requirements.md`
3. `docs/CONTRIBUTOR.md`
4. `AGENTS.md`
5. `docs/projects/protocol-governed/lmstudio-findings-and-live-test-plan.md`

## 1. Objective

Implement the local prompting contract defined in `local-prompting-requirements.md` so Orket can run provider-model combinations (primarily Ollama and LM Studio/OpenAI-compatible paths) with deterministic prompt rendering, strict output conformance, repeatable repair behavior, and auditable template safety.

This plan assumes 2026 local-runtime fragmentation across model families (for example DeepSeek-R1, Llama variants, and Qwen variants) and enforces provider-model profile handling as the stability boundary.

Primary outcome:
1. provider-model profile contract acts as the runtime "Local Inference BIOS",
2. no silent fallback or role/template ambiguity in strict paths,
3. measurable conformance gates before promotion.

## 1a. Execution Status (2026-03-06)

Completed increment:
1. LP-01 profile contract scaffolding landed in `orket/runtime/local_prompt_profiles.py`.
2. Canonical profile registry seed landed in `model/core/contracts/local_prompt_profiles.json`.
3. Resolver/schema test coverage landed in `tests/runtime/test_local_prompt_profiles.py`.
4. Runtime call-path policy wiring landed:
   - provider policy resolver at `orket/adapters/llm/local_prompting_policy.py`
   - model adapter application in `orket/adapters/llm/local_model_provider.py`
   - turn-context pass-through in `orket/application/workflows/turn_executor_ops.py`
5. Runtime-policy/settings control surfaces landed:
   - `local_prompting_mode`
   - `local_prompting_allow_fallback`
   - `local_prompting_fallback_profile_id`
6. Conformance/drift/audit scripts landed:
   - `scripts/protocol/run_local_prompting_conformance.py`
   - `scripts/protocol/compare_local_prompting_profile_drift.py`
   - `scripts/protocol/summarize_local_prompting_failures.py`
   - `scripts/protocol/audit_prompt_templates.py`
7. Local prompting error registry seed landed in `orket/runtime/error_codes.py`.
8. Live verification captures landed under `benchmarks/results/protocol/local_prompting/live_verification/` for:
   - Ollama `qwen2.5-coder:7b` (strict conformance currently failing parse/tool thresholds),
   - LM Studio `qwen3.5-4b` (strict conformance passing in single-case smoke).
9. LP-09/LP-10 strict validator expansion landed:
   - profile-scoped anti-meta diagnostics with deterministic leaf/family metadata in `orket/application/workflows/turn_contract_validator.py`,
   - thinking-block prefix stripping helper in `orket/application/workflows/turn_response_parser.py`,
   - profile telemetry propagation for thinking policy + intro denylist in `orket/adapters/llm/local_prompting_policy.py`.
10. LP-12/LP-13 gate hardening landed in `scripts/protocol/run_local_prompting_conformance.py`:
    - corpus profile selector (`--suite smoke|promotion`),
    - per-task case-count overrides,
    - explicit threshold controls for strict-json/tool-call + anti-meta rates,
    - deterministic anti-meta rate capture in conformance artifacts.
11. LP-16 template-source ingestion landed in `scripts/protocol/audit_prompt_templates.py`:
    - optional profile/template source path ingestion (`template_source_path`/`template_path`),
    - structured evidence of loaded sources in audit artifacts.
12. New tests landed for strict anti-meta and ingestion paths:
    - `tests/application/test_turn_contract_validator.py`
    - `tests/application/test_turn_response_parser.py`
    - `tests/runtime/test_local_prompt_profiles.py`
    - `tests/scripts/test_run_local_prompting_conformance.py`
    - `tests/scripts/test_audit_prompt_templates.py`
13. Live verification rerun against real providers after LP-09/LP-10 and gate updates:
    - preflight PASS: Ollama `qwen2.5-coder:7b`, LM Studio `qwen3.5-4b`,
    - smoke conformance evidence refreshed under `benchmarks/results/protocol/local_prompting/live_verification/`,
    - promotion-suite code path validated live on LM Studio using `--suite promotion` with case overrides.
14. LM Studio-specific findings and live-test-heavy remediation plan documented at:
    - `docs/projects/protocol-governed/lmstudio-findings-and-live-test-plan.md`
15. LM Studio session-mode live matrix expanded with high-volume runs:
    - `none` qualification: `200` strict JSON + `200` tool-call (all pass),
    - `context` qualification: `200` strict JSON + `200` tool-call (all pass),
    - `fixed` reduced qualification: `80` strict JSON + `80` tool-call (all pass),
    - zero anti-meta chatter/fence and zero summarized failures across these runs.
16. Ollama strict JSON format binding landed for strict task classes in provider adapter:
    - `orket/adapters/llm/local_model_provider.py` now requests `format="json"` for `strict_json` and `tool_call`,
    - telemetry now records `ollama_request_format` and fallback usage.
17. Ollama blocker revalidation (live) now passes:
    - baseline evidence (pre-fix): `benchmarks/results/protocol/local_prompting/ollama_blocker_baseline_2026-03-06/` (`strict_json/tool_call=0.0`, anti-meta `1.0/1.0`),
    - candidate smoke evidence (post-fix): `benchmarks/results/protocol/local_prompting/ollama_blocker_candidate_2026-03-06/` (`20/20` strict + `20/20` tool),
    - qualification evidence: `benchmarks/results/protocol/local_prompting/ollama_qualification_200_2026-03-06/` (`200/200` strict + `200/200` tool),
    - promotion evidence: `benchmarks/results/protocol/local_prompting/ollama_promotion_2026-03-06/` (`1000/1000` strict + `500/500` tool),
    - failure summary: `benchmarks/results/protocol/local_prompting/ollama_promotion_2026-03-06/conformance/ollama/ollama.qwen.chatml.v1/failure_summary.json` (`total_failures=0`).
18. LP-12/LP-13/LP-16 promotion decision package gate landed:
    - script: `scripts/protocol/check_local_prompting_promotion_readiness.py`
    - deterministic profile gate output:
      `benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json`
    - active provider profiles evaluated green:
      - `ollama.qwen.chatml.v1`
      - `openai_compat.qwen.openai_messages.v1`

Promotion blocker status:
1. Cleared for Ollama `qwen2.5-coder:7b` under current profile and strict gates.
2. Cleared for LM Studio/OpenAI-compat `qwen3.5-4b` under current profile and strict gates.
3. M8 promotion decision package is complete with deterministic readiness output.

## 2. Scope and Non-Goals

In scope:
1. LP-01 through LP-16 implementation and validation surfaces.
2. Adapter behavior in `ollama` and `openai_compat` (`lmstudio`) backends.
3. Deterministic strict JSON/tool-call conformance pathways.
4. Profile-driven role/template/stop/sampling enforcement.
5. Template integrity audit for non-`openai_messages` profiles.

Out of scope:
1. GUI installers/wizards for local model runtimes.
2. Model quality optimization beyond protocol conformance.
3. Broad benchmark redesign unrelated to prompting contract.

## 3. Delivery Principles

1. No implementation work is considered complete without real runtime execution evidence for integration changes.
2. Strict paths fail closed on profile, template, or validation ambiguity.
3. Profile behavior is mechanical and versioned; no "best effort" implicit mapping.
4. Changes land in small, test-backed slices with rollback notes.
5. Deterministic mode must prioritize reproducibility over throughput.

## 4. Source-of-Truth Boundaries

1. Runtime governance: `docs/projects/protocol-governed/requirements.md`
2. Local prompting contract: `docs/projects/protocol-governed/local-prompting-requirements.md`
3. Plan of execution: this file
4. Runtime policy persistence and precedence: `orket/application/services/runtime_policy.py`
5. Provider invocation behavior:
   - `orket/adapters/llm/local_model_provider.py`
   - `orket/streaming/model_provider.py`
6. Prompt assembly and strict validation path:
   - `orket/application/workflows/turn_message_builder.py`
   - `orket/application/workflows/orchestrator_ops.py`
   - `orket/application/workflows/turn_response_parser.py`
   - `orket/application/workflows/turn_contract_validator.py`
7. Task class routing source of truth:
   - `orket/application/workflows/orchestrator_ops.py` routing entrypoint,
   - profile contract task-class policy in `local-prompting-requirements.md`.

## 5. Requirement Traceability Matrix

| Requirement | Implementation surfaces | Evidence |
|---|---|---|
| LP-01 | profile registry + loader + resolver + runtime policy exposure | profile schema tests, resolver tests |
| LP-02 | render canonicalization utility + hash generation | canonicalization unit tests, hash parity tests |
| LP-03 | role-set enforcement in adapter + message builder | role mismatch tests |
| LP-04 | stop binder + per-task stop ordering | must-stop conformance cases |
| LP-05 | strict payload contract builder + task class routing | strict JSON/tool-call parser tests + task class routing tests |
| LP-06 | prefill capability + strategy routing | backend capability tests |
| LP-07 | bounded history policy engine + token budget calculator | history trimming determinism tests |
| LP-08 | sampling bundle binding + capability recording | sampling conformance artifacts + task class routing tests |
| LP-09 | deterministic repair loop + error code registry mapping | retry-loop determinism tests |
| LP-10 | anti-meta + thinking block handling | extraneous text/think block tests |
| LP-11 | telemetry field emission | integration telemetry assertions |
| LP-12 | provider conformance harness | run artifacts + summary JSON |
| LP-13 | upgrade drift comparison tooling | before/after compatibility report |
| LP-14 | fail-closed fallback behavior | fallback failure tests |
| LP-15 | render verification path(s) | expected-vs-observed hash comparisons |
| LP-16 | template integrity audit + whitelist gate | structured audit artifact |

## 6. Artifact Layout

Planned artifact root:
1. `benchmarks/results/protocol/local_prompting/`

Required artifact files:
1. `profiles/profile_registry_snapshot.json`
2. `profiles/profile_registry_snapshot.sha256`
3. `profiles/enabled_pack.json`
4. `profiles/error_code_registry_snapshot.json`
5. `conformance/<provider>/<profile_id>/strict_json_report.json`
6. `conformance/<provider>/<profile_id>/tool_call_report.json`
7. `conformance/<provider>/<profile_id>/anti_meta_report.json`
8. `conformance/<provider>/<profile_id>/sampling_capabilities.json`
9. `conformance/<provider>/<profile_id>/render_verification.json`
10. `conformance/<provider>/<profile_id>/capability_probe_method.json`
11. `conformance/<provider>/<profile_id>/suite_manifest.json`
12. `conformance/<provider>/<profile_id>/tokenizer_identity.json`
13. `drift/<date>/profile_delta_report.json`
14. `template_audit/<profile_id>/audit_report.json`
15. `template_audit/<profile_id>/whitelist_decision.json` (if applicable)

## 7. Execution Phases

### Phase 0: Baseline and Design Lock

Goals:
1. freeze contract fields and policy defaults before code changes,
2. define minimal supported profile set for first rollout.

Tasks:
1. Publish initial profile list for active providers:
   - `ollama`: at least one Llama profile, one Qwen profile, one DeepSeek profile.
   - `openai_compat` (`lmstudio`): mirrored set where available.
2. Define profile naming convention:
   - `<provider>.<model_family>.<variant>.<version>`
3. Define deterministic default strict task classes:
   - `strict_json`
   - `tool_call`
4. Define initial thinking policy defaults per profile.
5. Define task class routing rules:
   - routing authority location in workflow,
   - priority order when multiple task classes appear possible,
   - default routing to `concise_text` when no parseable contract is declared.
6. Define initial enabled profile pack:
   - pack ID example: `pack_local_v1`,
   - include only promotion-candidate profiles for first rollout.

Exit criteria:
1. stable profile IDs chosen and documented,
2. no unresolved field-name ambiguity.
3. task class routing rules frozen.
4. initial profile pack list fixed and versioned.

---

### Phase 1: Profile Registry and Validation (LP-01, LP-14)

Goals:
1. create single source of truth for provider-model profile contracts,
2. enforce strict schema validation and fail-closed behavior.

Tasks:
1. Add profile schema model(s) and validators:
   - required fields for LP-01,
   - field enum validation,
   - cross-field validation (`seed_policy` vs `seed_value`, thinking settings, stop maps).
2. Add registry loader with deterministic merge/override rules.
3. Add profile resolver:
   - input: provider + model + optional explicit override,
   - output: one resolved profile or explicit error.
4. Add fallback policy:
   - strict path: fail closed by default,
   - documented downgrade path only when explicitly configured.
5. Surface resolved `profile_id` and contract metadata into turn context.
6. Persist profile registry snapshot hash (`profile_registry_snapshot.sha256`) and include it in conformance metadata.

Code touchpoints:
1. `orket/application/services/runtime_policy.py`
2. `orket/adapters/llm/local_model_provider.py`
3. `orket/application/workflows/orchestrator_ops.py`
4. new module(s) under `orket/runtime/` or `orket/application/workflows/` for profile registry logic.

Tests:
1. schema validation accepts valid contracts and rejects invalid enums,
2. unknown provider/model in strict path returns deterministic failure,
3. explicit fallback configuration is honored and logged.

Exit criteria:
1. all strict calls resolve exactly one profile or fail with deterministic code,
2. no silent provider/model inference.

---

### Phase 2: Render Canonicalization and Hashing (LP-02, LP-11, LP-15)

Goals:
1. produce stable render hashes across environments,
2. ensure telemetry includes reproducible hash metadata.

Tasks:
1. Implement canonicalization utility:
   - line ending normalization to `\n`,
   - trailing whitespace handling,
   - optional Unicode normalization flag handling.
2. Compute `template_hash` over final rendered bytes (post-template render, post-canonicalization).
3. Emit `template_hash_alg` (default `sha256`) in telemetry.
4. Add render verification comparator:
   - expected hash vs observed hash when provider path supports it.
5. Add byte-count telemetry (`rendered_prompt_byte_count`).
6. Define provider render verification mapping and persist method used:
   - Ollama: deterministic local renderer hash and/or raw request parity path.
   - LM Studio/OpenAI-compat: observed request payload hash and local renderer parity where template metadata is available.
   - vLLM future lane: request payload hash plus renderer class parity hooks when enabled.

Code touchpoints:
1. `orket/application/workflows/turn_message_builder.py`
2. `orket/adapters/llm/local_model_provider.py`
3. `orket/streaming/model_provider.py`
4. shared hashing utility module.

Tests:
1. hash stability across CRLF/LF inputs,
2. hash difference when template content changes,
3. render verification path assertions (when available).

Exit criteria:
1. hash parity reproducible in repeated runs,
2. telemetry includes `template_hash`, `template_hash_alg`, `template_version`, byte count.
3. render verification artifact captures method and evidence path per provider/profile.

---

### Phase 3: Role/Template/Tool Contract Enforcement (LP-03, LP-05)

Goals:
1. prevent role drift and hidden role remapping,
2. ensure tool-call contract is explicit and profile-scoped.

Tasks:
1. Enforce `allowed_roles` in outbound payload construction.
2. Enforce `system_prompt_mode`:
   - `native`: normal role flow,
   - `user_injection`: deterministic wrapper in first user message; no outbound system role.
3. Bind tool-call serialization to `tool_contract`:
   - manifest injection channel (`system`/`user`/`none`),
   - schema identifier binding,
   - `tool_result_role`.
4. Add strict-mode rejection for undeclared role usage.

Code touchpoints:
1. `orket/application/workflows/turn_message_builder.py`
2. `orket/application/workflows/orchestrator_ops.py`
3. `orket/adapters/llm/local_model_provider.py`
4. `orket/application/workflows/turn_contract_validator.py`

Tests:
1. role mismatch rejected deterministically,
2. `user_injection` wrapper deterministic and idempotent,
3. undeclared tool-call shape rejected.

Exit criteria:
1. outbound role set always profile-compliant,
2. strict mode cannot silently normalize unknown roles.

---

### Phase 4: Stop Binding and Deterministic Termination (LP-04)

Goals:
1. make stop behavior deterministic and verifiable,
2. ensure "must-stop" regression coverage.

Tasks:
1. Implement stop binder by `(profile, task_class)`.
2. Deterministic stop order:
   - sentinel stops,
   - template EOT stops,
   - provider default EOS.
3. Add per-profile override for alternate ordering with explicit flag.
4. Add must-stop conformance prompt cases.
5. Record effective stop set in telemetry.
6. Define template EOT stop source precedence:
   - profile explicit stops,
   - model metadata token set,
   - provider defaults.
7. Record source attribution for each bound stop in telemetry and conformance artifacts.

Code touchpoints:
1. `orket/adapters/llm/local_model_provider.py`
2. `orket/application/workflows/orchestrator_ops.py`
3. `orket/streaming/model_provider.py`

Tests:
1. earliest encountered stop terminates (provider permitting),
2. must-stop case fails when stop not honored,
3. effective stop telemetry matches runtime request.

Exit criteria:
1. stop behavior measurable per task class,
2. deterministic binder output for identical inputs.

---

### Phase 5: Context Budget and History Policy Engine (LP-07)

Goals:
1. deterministic context trimming before provider call,
2. stable behavior across tokenizers and runtimes.

Tasks:
1. Implement versioned history policy registry:
   - `bounded_head_tail_v1`
   - `seat_only_bounded_head_tail_v1`
   - `none_v1`
2. Implement alias mapping:
   - `bounded_head_tail` -> `bounded_head_tail_v1`
3. Token budgeting:
   - use resolved profile tokenizer (or declared equivalent),
   - deterministic tie-break ordering.
4. Record token counter source in conformance artifacts.
5. Ensure strict tool paths strip non-essential context.
6. Keep head prefix byte-stable across turns under `bounded_head_tail` policies to maximize prefix-cache hit rates where provider/runtime supports prefix caching (byte-stable means post-canonicalization bytes per LP-02, not pre-template message objects).
7. Deterministic token counter failure behavior:
   - strict paths fail closed with deterministic error code when tokenizer source unavailable,
   - non-strict downgrade only if explicitly allowed by policy.

Code touchpoints:
1. `orket/application/workflows/orchestrator_ops.py`
2. `orket/application/workflows/turn_message_builder.py`
3. provider adapter layer for token counting support.

Tests:
1. same context input => same trimmed output,
2. seat-only mode excludes non-seat transcript rows,
3. context budget never exceeds configured limit under chosen tokenizer,
4. tokenizer source unavailable path behaves deterministically (strict fail-closed, optional non-strict downgrade).

Exit criteria:
1. deterministic trimming under repeated runs,
2. conformance artifacts include tokenizer source metadata.

---

### Phase 6: Sampling Bundles and Provider Capability Capture (LP-06, LP-08)

Goals:
1. bind sampling settings by task class via profile contract,
2. record actual provider handling (honored/ignored/clamped/approximated).

Tasks:
1. Implement per-task sampling binder:
   - `temperature`, `top_p`, `top_k`, `repeat_penalty`, `max_output_tokens`, seed.
2. Seed semantics:
   - `fixed`: send explicit seed value,
   - `provider_default`: omit seed, record determinism behavior.
3. Implement capability capture in conformance output for each sampling field.
4. Enforce strict JSON repeat penalty safe-range exception process.
5. Capability detection method:
   - compare requested params to provider response metadata when available,
   - otherwise run controlled fixed-prompt probes and classify as honored/ignored/clamped/approximated.

Code touchpoints:
1. `orket/adapters/llm/local_model_provider.py`
2. `orket/streaming/model_provider.py`
3. conformance harness tooling in `scripts/`.

Tests:
1. sampling binder deterministic for same profile/task input,
2. field-level capability capture populated for all required fields,
3. strict-range exception path requires explicit profile evidence.

Exit criteria:
1. no ad-hoc sampling in strict paths,
2. artifacts report actual provider behavior, not assumptions.

---

### Phase 7: Strict Validation Surface + Deterministic Repair (LP-09, LP-10)

Goals:
1. block protocol chatter and hidden payload tricks,
2. make repair loop deterministic and bounded.

Tasks:
1. Implement anti-meta validators:
   - payload-only ASCII whitespace rule,
   - markdown fence rejection,
   - profile-scoped intro phrase denylist.
2. Thinking block policy:
   - honor `allows_thinking_blocks` + `thinking_block_format`,
   - enforce permitted location (before payload only),
   - reject if blocks appear after payload begins.
3. Prefer provider-native thinking suppression for strict tasks where available.
4. Deterministic repair loop:
   - fixed error registry mapping,
   - deterministic reprompt builder from code + short detail + excerpt hash,
   - bounded retries with deterministic terminal outcome.
5. For providers exposing native thinking controls (for example Ollama), strict `strict_json` and `tool_call` paths prioritize `think=false` before manual block filtering.
6. Establish fixed error-code registry source file and one-to-one mapping:
   - runtime file: `orket/runtime/error_codes.py` (or equivalent finalized path),
   - artifact snapshot: `profiles/error_code_registry_snapshot.json`.
7. Add deterministic recovery playbook coverage for high-frequency strict failures:
   - markdown fence contamination,
   - thinking overflow/placement violations,
   - schema extra keys.

Initial deterministic error mapping table (seed set):

Leaf codes MUST map 1:1 to a single LP-09 family for stable aggregation.

| Error family (LP-09) | Leaf code | Detection surface | Recovery strategy |
|---|---|---|---|
| `EXTRANEOUS_TEXT` | `ERR_JSON_MD_FENCE` | `turn_response_parser` | remove markdown fence wrappers and retry with payload-only emphasis |
| `EXTRANEOUS_TEXT` | `ERR_THINK_OVERFLOW` | `turn_contract_validator` | apply native `think=false` when available; otherwise enforce think-block location policy and retry |
| `SCHEMA_MISMATCH` | `ERR_SCHEMA_EXTRA_KEYS` | `turn_contract_validator` | retry with schema-key-only corrective constraint |

Code touchpoints:
1. `orket/application/workflows/turn_response_parser.py`
2. `orket/application/workflows/turn_contract_validator.py`
3. `orket/application/workflows/turn_message_builder.py`
4. `orket/adapters/llm/local_model_provider.py`

Tests:
1. thinking block before payload accepted only if profile permits,
2. thinking block after payload start rejected,
3. parser errors map to stable repair loop behavior,
4. strict task class with provider-native thinking suppression avoids think-block parse pollution.

Exit criteria:
1. strict parse rates meet targets in conformance suites,
2. no infinite or non-deterministic retry behavior.

---

### Phase 8: Telemetry Surfaces and Observability (LP-11)

Goals:
1. expose all required telemetry fields for reproducibility,
2. ensure strict-mode diagnostics are complete without secret leakage.

Tasks:
1. Emit all LP-11 fields from runtime turn context and response metadata.
2. Ensure telemetry carries `profile_id`, `task_class`, stop and sampling bundles.
3. Mask sensitive content while keeping reproducibility metadata.
4. Add UI/API field pass-through if necessary.

Code touchpoints:
1. `orket/application/workflows/orchestrator_ops.py`
2. `orket/interfaces/` response surfaces
3. `orket/adapters/llm/local_model_provider.py`

Tests:
1. telemetry completeness tests for strict mode,
2. no prompt-content leak assertions for sensitive fields.

Exit criteria:
1. reproducibility metadata present for all strict-mode runs.

---

### Phase 9: Conformance Harness and Drift Gates (LP-12, LP-13)

Goals:
1. operationalize measurable conformance thresholds,
2. block promotions on regression.

Tasks:
1. Build conformance runner scripts for:
   - strict JSON suite (1000 prompts),
   - tool-call suite (500 prompts),
   - anti-meta and must-stop suites.
2. Capture per-profile/provider reports.
3. Add drift comparator for before/after upgrades.
4. Add policy gate script:
   - fails when thresholds miss,
   - emits top failure families.
5. Add metric tiers in conformance outputs:
   - `L0` (safety): role enforcement + template integrity gate state,
   - `L1` (syntax): JSON/tool-call validity rates,
   - `L2` (behavior): must-stop compliance + repeat-penalty stability.
6. Emit deterministic suite manifest per run:
   - suite version,
   - test case IDs,
   - selection RNG seed (if applicable),
   - prompt corpus hash,
   - profile registry snapshot hash.

Planned script surfaces:
1. `scripts/protocol/run_local_prompting_conformance.py`
2. `scripts/protocol/compare_local_prompting_profile_drift.py`
3. `scripts/protocol/summarize_local_prompting_failures.py`
4. `scripts/protocol/check_local_prompting_promotion_readiness.py`

Tests:
1. script unit tests under `tests/scripts/`,
2. schema validation for generated artifacts.

Exit criteria:
1. promotion gate returns pass/fail deterministically from artifacts.
2. suite manifest is present for every conformance run used in promotion decisions.

---

### Phase 10: Template Integrity Audit and Whitelist Gate (LP-16)

Goals:
1. treat template content as untrusted for non-OpenAI-message paths,
2. fail closed on suspicious constructs.

Tasks:
1. Implement template scanner for:
   - conditional branches based on message content,
   - hidden role remapping,
   - undeclared tool instruction injection,
   - regex/string trigger-based alternate render paths.
2. Include known high-risk template-injection patterns in baseline detectors:
   - `{{ self.__init__.__globals__ }}` and close variants,
   - built-in loader/eval/import escape patterns.
   - These baseline detectors apply only to Jinja-like template engines; audit MUST first identify `template_engine` and then run engine-appropriate detectors.
3. Emit structured audit artifact:
   - `template_engine` (for example `jinja2`, `go_template`, `unknown`),
   - detected constructs,
   - pass/fail decision,
   - whitelist references.
4. Gate profile promotion on pass or approved whitelist.
5. Add audit rerun requirement when template changes.

Planned script surface:
1. `scripts/protocol/audit_prompt_templates.py`

Tests:
1. malicious template fixtures are rejected,
2. benign templates pass with no suspicious flags,
3. whitelist reference enforcement works.

Exit criteria:
1. non-`openai_messages` profile promotion blocked without audit pass.
2. audit artifact contains machine-readable construct list and decision provenance.

---

### Phase 11: Live Verification and Rollout

Goals:
1. validate behavior in real runtime paths,
2. stage rollout with explicit rollback controls.

Rollout steps:
| Mode | Behavior |
|---|---|
| `shadow` | Resolve profile, compute hashes, run validators in observe-only mode, emit telemetry; no non-safety rejection. |
| `compat` | Validate and record failures; reject only hard safety failures; emit operator warnings and full artifacts. |
| `enforce` | Strict validator controls active; fail closed on profile/template/validation ambiguity. |

Runtime policy toggle:
1. `local_prompting_mode` (`shadow`, `compat`, `enforce`)

Hard safety failures in compat mode are limited to:
1. template integrity audit failure (LP-16) for non-`openai_messages` profiles,
2. profile resolution ambiguity in strict task classes (LP-01/LP-14),
3. tool-call execution attempt with invalid or unknown tool name,
4. forbidden role injection (LP-03) in tool paths.

All other validator failures in compat mode are record-and-warn (non-reject) unless separately elevated by explicit policy.

Required live verification evidence:
1. real run on Ollama strict JSON profile,
2. real run on LM Studio/OpenAI-compat strict JSON profile,
3. at least one tool-call profile per provider,
4. explicit primary path observed (no fallback),
5. failures captured with exact failing step and error.
6. mode-specific behavior observed and recorded for each rollout mode.

Exit criteria:
1. threshold compliance met,
2. operator sign-off recorded with artifact bundle links,
3. rollback path validated.

## 8. Test Plan (Detailed)

Unit tests:
1. profile schema validation and cross-field constraints.
2. role/set enforcement and user-injection wrapper.
3. stop binder ordering and must-stop trigger logic.
4. canonicalization and hash repeatability.
5. thinking-block parser and anti-meta validators.
6. deterministic repair loop state transitions.

Integration tests:
1. end-to-end strict JSON from prompt build to parse acceptance.
2. end-to-end tool-call with profile tool contract.
3. fallback fail-closed behavior for unknown profile.
4. telemetry completeness for strict paths.

Live tests:
1. Ollama strict JSON run.
2. OpenAI-compatible LM Studio strict JSON run.
3. one tool-call run on each provider path.
4. must-stop runtime behavior with sentinel.

Soak tests:
1. repeated strict JSON campaigns with fixed seed policy where supported.
2. drift runs before/after provider/model/template updates.
3. prefix-cache stability runs for history-policy consistency (future lane where applicable).

## 9. Metrics and Gates

Conformance thresholds:
1. strict JSON parse pass rate >= 98% on 1000-case suite.
2. tool-call shape correctness >= 99% on 500-case suite.
3. protocol chatter rate < 2% in strict modes.
4. deterministic repair-loop convergence bounded by configured retry cap.

Tiered gate interpretation:
1. `L0` safety failures block promotion immediately.
2. `L1` syntax failures block strict promotion and require remediation.
3. `L2` behavior regressions require review; repeated or severe regressions block promotion per policy.

Promotion blockers:
1. profile resolution ambiguity,
2. missing telemetry fields,
3. template audit fail without approved whitelist,
4. regression against thresholds.

## 10. Risk Register

1. Risk: provider silently ignores sampling controls.
   - Mitigation: capture per-field behavior in conformance artifacts.
2. Risk: tokenizer mismatch causes context overflow.
   - Mitigation: record token counter source, tokenizer version/identity in conformance artifacts, and enforce profile tokenizer compatibility.
3. Risk: hidden template logic bypasses contract.
   - Mitigation: LP-16 audit + fail closed + whitelist governance.
4. Risk: native provider behavior changes across updates.
   - Mitigation: LP-13 drift gate and mandatory comparison artifacts.
5. Risk: strict enforcement increases retries/latency.
   - Mitigation: tune profile-level defaults, use native thinking suppression where safe, optimize bounded history.

## 11. Rollback Plan

1. Keep previous profile registry snapshot and artifact baseline.
2. Support per-profile rollback toggle in runtime policy.
3. On rollback:
   - restore previous profile version,
   - rerun conformance quick suite,
   - verify telemetry continuity.
4. Record rollback reason and failure signature in operator artifact bundle.

## 12. Milestone Checklist

1. M1: Profile registry + resolver + fail-closed fallback complete.
2. M2: Hashing/canonicalization + telemetry completeness complete.
3. M3: Role/stop/context/sampling binders complete.
4. M4: Anti-meta + thinking policy + repair loop complete.
5. M5: Conformance harness + drift gates complete.
6. M6: Template integrity audit + whitelist gate complete.
7. M7: Live verification evidence complete for active providers and rollout modes.
8. M8: Promotion decision package complete.
9. Milestone status (2026-03-06): M1-M8 complete for active provider profiles.

## 13. Definition of Done

This effort is complete when:
1. LP-01 through LP-16 have concrete runtime surfaces and test coverage.
2. Conformance artifacts meet threshold gates.
3. Live runs prove real provider paths and strict contract behavior.
4. Template audit/whitelist flow is operational.
5. Rollback workflow is tested and documented.

Current state (2026-03-06):
1. Definition of Done is satisfied for active local providers (`ollama`, `openai_compat`/LM Studio).
2. Remaining work is monitor-mode freshness: rerun conformance/drift/promotion-readiness gates on provider/model/runtime-policy changes.
