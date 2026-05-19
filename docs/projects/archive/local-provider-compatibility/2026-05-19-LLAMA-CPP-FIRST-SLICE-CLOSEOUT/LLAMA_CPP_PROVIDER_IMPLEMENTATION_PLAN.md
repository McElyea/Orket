# llama.cpp Provider Implementation Plan

Last updated: 2026-05-19
Status: Active implementation plan
Implementation request: accepted on 2026-05-18
Owner: Orket Core
Requirements: `docs/projects/archive/local-provider-compatibility/2026-05-19-LLAMA-CPP-FIRST-SLICE-CLOSEOUT/LLAMA_CPP_PROVIDER_REQUIREMENTS.md`
Contract authority: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
Contract delta: `docs/architecture/CONTRACT_DELTA_LLAMA_CPP_FIRST_SLICE_2026-05-18.md`
Operator source-build note: `docs/projects/archive/local-provider-compatibility/2026-05-19-LLAMA-CPP-FIRST-SLICE-CLOSEOUT/LLAMA_CPP_SOURCE_BUILD_OPERATOR_NOTE.md`

## Authority Posture

This plan admits a live implementation lane.
It does not yet admit `llama_cpp` as a promoted provider and does not claim runtime support.

Completion requires real provider proof against an operator-managed `llama-server` with a real GGUF model.
Binary presence, import success, structural tests, and endpoint reachability alone are not enough.

## 2026-05-19 Structural Implementation Checkpoint

Implemented but unpromoted:
1. `llama_cpp` is an allowed requested provider token while using `openai_compat` as the transport backend.
2. Provider telemetry preserves `requested_provider=llama_cpp` and `provider_name=llama_cpp`.
3. Default llama.cpp base URL resolves to `http://127.0.0.1:8080/v1`.
4. Provider and provider-model quarantine cover `llama_cpp`.
5. GGUF inventory is bounded to the configured model root and records alias, path, size, digest status, and optional SHA256.
6. `/v1/models` preflight supports `--provider llama_cpp` and fails blocked warmup paths.
7. `llama_cpp.qwen.chatml.v1` resolves deterministically for `qwen3.6-27b-q4_k_m`.
8. Runtime invocation routes through OpenAI-compatible chat completions while preserving llama.cpp lineage.
9. Request-shape telemetry records `render_observability_classification=message_payload_audited`, model alias, message payload shape, request payload byte count, effective stops, and sampling bundle.
10. Local prompting conformance and promotion-readiness scripts accept the llama.cpp profile, but promotion remains blocked without live conformance artifacts.

Observed proof state:
1. Structural and contract tests pass for provider identity, GGUF inventory, profile resolution, request-shape telemetry, preflight behavior, provider truth, and conformance-script support.
2. Local GGUF inventory resolves `D:\Models\GGUF\Qwen3.6-27B-Q4_K_M.gguf` with size `16817244384` and `digest_status=pending`.
3. Live provider preflight on 2026-05-19 with `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider llama_cpp --model-id qwen3.6-27b-q4_k_m --timeout 5 --no-auto-load-local-model` recorded `OBSERVED_PATH=blocked` and `OBSERVED_RESULT=environment blocker` because the llama.cpp OpenAI-compatible endpoint was unreachable.
4. Live strict JSON and tool-call smoke remain pending until an operator-managed `llama-server` exposes the target alias.

## First Target Model Record

1. `repo_id`: `unsloth/Qwen3.6-27B-GGUF`
2. `filename`: `Qwen3.6-27B-Q4_K_M.gguf`
3. `alias`: `qwen3.6-27b-q4_k_m`
4. `profile_id`: `llama_cpp.qwen.chatml.v1`
5. `model_root`: `D:\models\GGUF`
6. `remote_expected_sha256`: `5ed60d0af4650a854b1755bd392f9aef4872643dc25a254bc68043fa638392a0`
7. `local_digest_status_at_start`: `pending`
8. `local_digest_algorithm`: `sha256`
9. `source_url`: `https://huggingface.co/unsloth/Qwen3.6-27B-GGUF/blob/main/Qwen3.6-27B-Q4_K_M.gguf`
10. `source_revision`: `82d411acf4a06cfb8d9b073a5211bf410bfc29bf`
11. `source_license`: `apache-2.0`
12. `remote_size_bytes`: `16817244384`
13. `remote_size_display`: `16.8 GB`
14. `xet_hash`: `85a68868db9ae3eac97b20a123249c5837d43692de58cd3dafd1fbe4d5725b34`
15. `source_verification_artifact`: `docs/projects/archive/local-provider-compatibility/2026-05-19-LLAMA-CPP-FIRST-SLICE-CLOSEOUT/llama_cpp_first_target_model_source_verification_2026-05-18.json`
16. `initial_context_size`: `8192`
17. `hardware_envelope`: `local Windows workstation; operator-managed llama.cpp build; no portability claim`
18. `gpu_offload_policy`: `implementation-default unless later specified`
19. `source_verification`: Hugging Face model page, API listing, resolve HEAD headers, and range headers verified the repo, file name, revision, license, remote size, Xet hash, and remote expected SHA256 during planning.
20. `local_file_presence_at_retarget`: `present_unverified`
21. `local_file_size_observed_at_retarget`: `16817244384`
22. `local_file_size_matches_remote`: `true`
23. `operator_source_build_note`: `docs/projects/archive/local-provider-compatibility/2026-05-19-LLAMA-CPP-FIRST-SLICE-CLOSEOUT/LLAMA_CPP_SOURCE_BUILD_OPERATOR_NOTE.md`

Model acquisition remains operator-managed for this slice.
No Hugging Face download helper is admitted.

## Scope

In scope:
1. First-class `llama_cpp` provider token.
2. Reuse of OpenAI-compatible HTTP plumbing only where provider lineage remains `llama_cpp`.
3. Configurable base URL, defaulting to `http://127.0.0.1:8080/v1`.
4. Configurable GGUF model root, with `D:\models\GGUF` as the local fixture.
5. GGUF inventory with `digest_status`.
6. Exactly one Qwen-family profile: `llama_cpp.qwen.chatml.v1`.
7. JSON-wrapper tool-call mode.
8. `/v1/models` preflight.
9. Strict JSON and tool-call smoke conformance.
10. Promotion-readiness regeneration before any promoted-profile claim.

Out of scope:
1. Starting, stopping, supervising, or auto-loading `llama-server`.
2. Downloading models.
3. Hugging Face helper tooling.
4. Native llama.cpp tool-calling admission.
5. Broad model-family support.
6. Direct `/completion` or raw-prompt support.

## Implementation Workstreams

### Workstream 1 - Provider Identity and Runtime Target

Tasks:
1. Add `llama_cpp` to allowed provider selection without collapsing requested provider telemetry into `openai_compat`.
2. Preserve `canonical_provider` or transport backend separately from `requested_provider`.
3. Add default base URL resolution for `llama_cpp`.
4. Extend provider quarantine and provider/model quarantine handling to cover `llama_cpp`.
5. Update provider truth artifacts only after structural tests and blocked-path behavior are covered.

Proof:
1. Contract tests for unknown-provider fail-closed behavior.
2. Contract tests showing `requested_provider=llama_cpp` and provider lineage remain visible.
3. Structural tests for quarantine behavior.

### Workstream 2 - GGUF Inventory

Tasks:
1. Add a configurable GGUF model root.
2. Inventory `.gguf` files under the configured root only.
3. Use `Path.is_relative_to()` for containment checks.
4. Record file path, alias, size, and `digest_status`.
5. Treat empty inventory as `blocked`.
6. Do not block preflight on full-file hashing when `digest_status` is `pending` or `skipped_by_policy`.

Proof:
1. Contract tests for model-root containment and empty inventory.
2. Contract tests for all digest states: `missing`, `pending`, `computed`, `failed`, `skipped_by_policy`.
3. Integration test using temporary GGUF-named files without treating them as live model proof.

### Workstream 3 - llama.cpp Preflight

Tasks:
1. Extend provider preflight to support `--provider llama_cpp`.
2. Probe `/v1/models` through the configured base URL.
3. Resolve the configured alias `qwen3.6-27b-q4_k_m`.
4. Report `blocked` when the endpoint is unreachable, the model list is empty, or the alias is absent.
5. Add smoke-stream support only if an Orket runtime path uses streaming for `llama_cpp`.
6. If first-slice invocation is non-streaming only, live proof MUST record streaming as `not_applicable` instead of silently omitting it.

Proof:
1. Integration tests for unreachable endpoint, empty model list, missing alias, and present alias.
2. Live preflight against operator-managed `llama-server` once the GGUF file is present and loaded.
3. Observed path must be recorded as `primary`, `fallback`, `degraded`, or `blocked`.

### Workstream 4 - Prompt Profile and Request Shape

Tasks:
1. Add `llama_cpp.qwen.chatml.v1` to the local prompt profile registry.
2. Bind the first profile to JSON-wrapper tool-call mode.
3. Record request-shape telemetry: `render_observability_classification=message_payload_audited`, provider, model alias, profile id, OpenAI-compatible message payload shape, request payload byte count, stop sequences, and sampling bundle.
4. Capture template-fidelity evidence at promotion time through one accepted path:
   - server-exposed template metadata,
   - llama.cpp template-analysis tooling,
   - Orket-owned tokenizer-template reproduction,
   - accepted waiver for the `message_payload_audited` path.
5. Do not claim per-run rendered-prompt-byte audit unless the runtime path exposes or deterministically reproduces it.

Proof:
1. Contract tests for profile resolution.
2. Contract tests for request-shape telemetry.
3. Template-audit artifact or explicit waiver before promotion-readiness claim.

### Workstream 5 - Adapter Invocation

Tasks:
1. Route `llama_cpp` calls through OpenAI-compatible chat completions while preserving provider lineage.
2. Apply profile-bound sampling and stop controls.
3. Keep `tool_call_mode=json_wrapper`.
4. Ensure parser and validator behavior matches the existing strict JSON and tool-call contracts.

Proof:
1. Contract tests for payload construction and provider lineage.
2. Integration tests with mocked HTTP failure modes only for negative-path behavior, not live success proof.
3. Live strict JSON and tool-call smoke conformance against the real llama.cpp endpoint.

### Workstream 6 - Promotion Gate

Tasks:
1. Regenerate local prompting promotion-readiness with the llama.cpp profile included only after live smoke proof exists.
2. Keep `llama_cpp` unpromoted if any proof gate is missing or blocked.
3. Update `CURRENT_AUTHORITY.md` only when the provider is admitted to a stronger authority state.

Proof:
1. Promotion-readiness output exists and records `llama_cpp.qwen.chatml.v1`.
2. Missing live evidence produces a blocked or not-ready result, not success.

## Verification Plan

Structural:
1. Provider token validation and unknown-provider fail-closed tests.
2. GGUF inventory containment and digest-status tests.
3. Profile registry and request-shape telemetry tests.
4. Provider truth artifact tests after artifact schema updates.

Integration:
1. Provider preflight negative paths.
2. `/v1/models` model-list handling against a local test HTTP service.
3. OpenAI-compatible request construction and parser/validator flow.

Live:
1. Operator starts llama.cpp.

Current operator-reported source-build launcher:

```powershell
powershell -ExecutionPolicy Bypass -File D:\llama.cpp-src\run-qwen36-27b-4090.ps1
```

The source-build operator note records the local `D:\llama.cpp-src` CUDA build, the retained `D:\llama.cpp\b9204-cuda-13.1` fallback, and the reported RTX 4090 Qwen3.6 27B smoke and benchmark results.

Fallback direct server shape:

```powershell
& "D:\llama.cpp\llama-server.exe" `
  -m "D:\models\GGUF\Qwen3.6-27B-Q4_K_M.gguf" `
  --host 127.0.0.1 `
  --port 8080 `
  --alias "qwen3.6-27b-q4_k_m" `
  --ctx-size 8192 `
  --jinja `
  --metrics
```

2. Run provider preflight with `ORKET_DISABLE_SANDBOX=1`.
3. Run local prompting smoke conformance for strict JSON and tool-call.
4. Regenerate promotion-readiness.
5. Record streaming smoke as `success` when a streaming runtime path is exercised, or `not_applicable` when first-slice invocation is non-streaming only.

Live proof must record:
1. observed path,
2. observed result,
3. model alias,
4. profile id,
5. GGUF file and digest status,
6. `render_observability_classification` and request-shape or rendered-template audit classification.

## Acceptance Gates

The lane can close only when:
1. `llama_cpp` is selectable without unknown-provider fallback.
2. `llama_cpp` telemetry remains distinct from generic OpenAI-compatible plumbing.
3. GGUF inventory is bounded to the configured model root.
4. `/v1/models` preflight resolves `qwen3.6-27b-q4_k_m`.
5. `llama_cpp.qwen.chatml.v1` resolves deterministically.
6. Strict JSON smoke succeeds on the real provider path.
7. Tool-call smoke succeeds on the real provider path using JSON-wrapper mode.
8. Promotion-readiness is regenerated and truthfully reports ready or blocked.
9. All authority docs changed by implementation are updated in the same change.

## Remaining Blockers

1. `D:\models\GGUF\Qwen3.6-27B-Q4_K_M.gguf` is present with observed size `16817244384`, but the local SHA256 digest has not been computed by an Orket proof path.
2. Operator-reported source-build smoke exists, but Orket-captured preflight against `http://127.0.0.1:8080/v1/models` is currently blocked because no endpoint is listening.
3. The first promotion-time template-fidelity path is not yet selected.
4. No live proof exists for the `llama_cpp` provider path.
