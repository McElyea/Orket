# llama.cpp Provider Requirements

Last updated: 2026-05-18
Status: Accepted requirements (implementation planning admitted; provider not promoted)
Owner: Orket Core
Roadmap lane: protocol-governed local provider compatibility expansion
Contract authority: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`

## Authority Posture

This packet defines requirements only.
It does not admit `llama_cpp` as an active provider, change runtime defaults, or make local GGUF model setup part of the Orket install path.

These requirements were accepted after revision on 2026-05-18.

Implementation request: accepted on 2026-05-18.

Implementation is governed by archived plan `docs/projects/archive/local-provider-compatibility/2026-05-19-LLAMA-CPP-FIRST-SLICE-CLOSEOUT/LLAMA_CPP_PROVIDER_IMPLEMENTATION_PLAN.md`.
Provider support remains unpromoted until live GGUF proof gates pass.

## Local Setup Snapshot

Observed local fixtures for this requirements lane:
1. `D:\llama.cpp` exists.
2. `D:\llama.cpp\llama-server.exe` exists.
3. Local `llama-server.exe --version` reported `version: 9134 (e75cd5efb)`, built with Clang 19.1.5 for Windows x86_64.
4. `D:\models\GGUF` exists.
5. No `.gguf` files were found under `D:\models\GGUF` during requirements drafting.
6. After first-target retargeting, `D:\models\GGUF\Qwen3.6-27B-Q4_K_M.gguf` was observed with size `16817244384`; local digest remains `pending`.
7. Operator-reported source-build setup exists at `D:\llama.cpp-src`, with CUDA build output under `D:\llama.cpp-src\build-cuda-vs2022\` and release fallback retained at `D:\llama.cpp\b9204-cuda-13.1`.
8. Operator-reported launcher and update helpers exist at `D:\llama.cpp-src\run-qwen36-27b-4090.ps1` and `D:\llama.cpp-src\update-build-cuda.ps1`.
9. Operator-reported source-build details are recorded in `docs/projects/archive/local-provider-compatibility/2026-05-19-LLAMA-CPP-FIRST-SLICE-CLOSEOUT/LLAMA_CPP_SOURCE_BUILD_OPERATOR_NOTE.md`.
10. `hf` and `huggingface-cli` were not found on `PATH` during requirements drafting.

These paths are operator-local fixtures for this lane, not portable defaults for every Orket installation.
Runtime implementation must keep paths configurable and must not hard-code this workstation layout into canonical runtime behavior.

## Scope

In scope:
1. First-class `llama_cpp` provider identity for local provider selection.
2. OpenAI-compatible `llama-server` chat-completions path as the first runtime mode.
3. GGUF model discovery and model-id resolution from an operator-provided model root.
4. Provider-model profile resolution for at least one qualified GGUF model family.
5. Local prompting conformance, preflight, template audit, and promotion-readiness support for `llama_cpp`.
6. Future optional operator helper support for Hugging Face GGUF downloads, after first provider proof exists.

Out of scope:
1. Training, fine-tuning, or quantizing models.
2. Vendoring llama.cpp binaries or GGUF files into this repository.
3. Automatically downloading large models during install, tests, or default runtime startup.
4. Treating `llama_cpp` as equivalent to LM Studio merely because both can expose OpenAI-compatible endpoints.
5. Direct `/completion` or raw prompt endpoints in the first accepted provider slice.
6. Non-loopback server exposure by default.
7. Hugging Face model download helper support in the first implementation slice.
8. Native llama.cpp tool-calling admission in the first implementation slice.

## Requirements

### LPCPP-01: Provider Identity

Runtime provider selection MUST admit a first-class requested provider token `llama_cpp`.

Requirements:
1. Unknown-provider policy MUST fail closed for misspelled or unsupported provider tokens.
2. Telemetry MUST preserve `requested_provider=llama_cpp`.
3. If the adapter reuses OpenAI-compatible HTTP plumbing internally, it MUST still record `provider_name=llama_cpp` or equivalent provider lineage.
4. `llama_cpp` MUST be independently supported by provider quarantine and provider/model quarantine policy.
5. Run-start provider truth artifacts MUST include `llama_cpp` only after implementation and proof exist.

### LPCPP-02: Endpoint Mode

The first provider slice MUST use llama.cpp server's OpenAI-compatible `/v1/chat/completions` path.

Requirements:
1. Default local base URL SHOULD be `http://127.0.0.1:8080/v1` when the provider is `llama_cpp`.
2. The base URL MUST be configurable.
3. The implementation MUST probe `/v1/models` or an equivalent server model-listing path before claiming provider readiness.
4. Streaming and non-streaming chat behavior MUST be checked separately if both are used by Orket paths.
5. API-key support MAY be accepted, but secrets MUST be passed through headers and never embedded in URLs, logs, traces, or artifacts.

### LPCPP-03: Server Lifecycle Boundary

The first implementation slice MUST treat `llama-server.exe` as operator-managed.
Server start/stop management is deferred to a later explicit lane.

Requirements:
1. Preflight MUST report `blocked` when the server is not reachable.
2. Preflight MUST not claim success merely because `llama-server.exe` exists on disk.
3. If Orket later manages the server process, runtime-reachable paths MUST use async-safe subprocess handling.
4. Any managed process launch MUST avoid shell-string command construction.
5. Managed lifecycle proof MUST demonstrate teardown in the same execution path.

Candidate operator-managed server shape:

```powershell
& "D:\llama.cpp\llama-server.exe" `
  -m "D:\models\GGUF\<model>.gguf" `
  --host 127.0.0.1 `
  --port 8080 `
  --alias "<model_id>" `
  --ctx-size 8192 `
  --jinja `
  --metrics
```

The exact command remains a requirements candidate until a model and hardware envelope are selected.

### LPCPP-04: GGUF Model Root and Inventory

The provider lane MUST separate local model inventory from runtime provider readiness.

Requirements:
1. The model root MUST be configurable, with `D:\models\GGUF` accepted as the local fixture for this lane.
2. No GGUF file may be tracked in this repository.
3. Model inventory MUST record file path, model alias, file size, and a digest or digest status.
4. `digest_status` MUST be one of `missing`, `pending`, `computed`, `failed`, or `skipped_by_policy`.
5. Provider preflight MUST NOT block on a full multi-GB digest when policy marks the digest as `pending` or `skipped_by_policy`, but promotion evidence MUST not claim a computed digest unless one exists.
6. Model inventory MUST not read outside the configured model root.
7. Path containment checks MUST use `Path.is_relative_to()` when implemented in Python.
8. Empty model inventory MUST produce `blocked`, not `success`.

### LPCPP-05: Deferred Model Acquisition Helper

Model acquisition MUST remain operator-managed for the first implementation slice.
No Hugging Face download helper is admitted in the first implementation slice.

If a later lane adds a Hugging Face download helper, the helper MUST remain optional and operator-approved.

Requirements:
1. No model download may run during install, default pytest, or default runtime startup.
2. The helper MUST accept explicit `repo_id`, filename or pattern, and destination directory.
3. The helper MUST write under the configured GGUF model root unless the operator explicitly chooses another path.
4. Hugging Face tokens MUST not be written to repo files, command logs, URLs, artifacts, or interpolated strings.
5. Missing `hf`, missing `huggingface-cli`, or missing Python `huggingface_hub` support MUST produce a clear blocked result.
6. Any rerunnable JSON output from the helper MUST use the repo diff-ledger writer.
7. Adding Hugging Face tooling to project dependencies requires same-change updates to install authority.

### LPCPP-06: First Qualified Model Family

The first accepted implementation MUST qualify exactly one Qwen-family GGUF provider-model profile before broad model-family expansion.

Rationale:
1. Existing local-prompting conformance and promotion evidence already centers on Qwen-family strict JSON and tool-call behavior.
2. The active local-prompting contract already defines a llama.cpp Qwen future lane.
3. A single family keeps first live proof narrow enough to trust.

Requirements:
1. The first profile MUST bind one concrete provider-model profile such as `llama_cpp.qwen.chatml.v1`.
2. Additional `llama_cpp.llama.inst.v1`, `llama_cpp.mistral.inst.v1`, or `llama_cpp.deepseek.custom.v1` profiles MUST not be promoted until they have separate conformance evidence.
3. Model selection MUST record exact GGUF filename, quantization label when available, source repo, and local file digest status.

### LPCPP-07: Prompt Profile and Template Fidelity

`llama_cpp` profiles MUST satisfy the active local-prompting contract before promotion.

Requirements:
1. Prompt behavior MUST resolve by `(provider, model)` profile, not by model name alone.
2. Qwen-family profiles MUST use tokenizer chat-template metadata where available.
3. Missing or ambiguous tokenizer chat-template metadata MUST fail closed for strict task classes unless an explicit profile override is accepted.
4. Request-shape telemetry MUST record `render_observability_classification=message_payload_audited`, the OpenAI-compatible message payload shape, selected provider-model profile, stop sequences, sampling bundle, model alias, and request payload byte count.
5. Template audit MUST run before promotion for non-`openai_messages` profiles.
6. Template-fidelity evidence MUST be captured at promotion time by at least one of:
   - server-exposed template metadata,
   - llama.cpp template-analysis tooling,
   - Orket-owned reproduction of the tokenizer chat template,
   - an explicit accepted waiver for the `message_payload_audited` path.
7. Per-run rendered prompt byte capture MUST NOT be required unless the selected runtime path exposes or deterministically reproduces the rendered prompt.
8. If rendered-prompt auditing is available, template hash, template version, rendered prompt byte count, and template hash algorithm MUST be captured.
9. `llama-template-analysis.exe` MAY be used as supporting evidence, but final Orket proof MUST come from the shipped Orket runtime path.

### LPCPP-08: Tool-Call Mode

The first `llama_cpp` provider slice MUST NOT assume provider-native tool calling.
Native llama.cpp tool calling is not part of first-slice acceptance.

Requirements:
1. First profile promotion SHOULD use `tool_call_mode=json_wrapper` unless live evidence proves native tools are supported and parser-safe on the selected llama.cpp build.
2. If native tools are admitted later, native tool names and tool-choice telemetry MUST be recorded and treated as authoritative by parser-side filtering.
3. Tool-call shape conformance MUST meet the active local-prompting threshold before promotion.
4. Native tool probes MAY be run experimentally, but successful or failed probes MUST NOT block first-slice JSON-wrapper acceptance.

### LPCPP-09: Sampling, Context, and Stop Controls

`llama_cpp` request binding MUST be profile-driven and observable.

Requirements:
1. `temperature`, `top_p`, `top_k`, `repeat_penalty`, `max_output_tokens`, and seed behavior MUST be bound through sampling bundles.
2. Provider handling for each sampling field MUST be recorded as `honored`, `ignored`, `clamped`, or `approximated`.
3. Context size MUST be explicit in server setup or provider telemetry.
4. Stop sequences MUST include strict sentinels for parseable task classes.
5. `--swa-full`, cache behavior, and context-shift-sensitive settings MAY be evaluated, but must not be required for first acceptance unless the selected model needs them for correctness.

### LPCPP-10: Verification and Proof

Implementation completion MUST include real provider proof.

Required proof levels:
1. Structural proof: provider token validation, runtime-target resolution, model inventory, profile resolution, telemetry shape.
2. Integration proof: preflight against a reachable llama.cpp server with a loaded GGUF model.
3. Live proof: strict JSON and tool-call conformance through shipped Orket runtime code using a real GGUF model.

Minimum live commands after implementation:
1. Provider preflight with streaming smoke when a `llama_cpp` streaming runtime path is exercised; if first-slice invocation is non-streaming only, live proof MUST record streaming as `not_applicable`.
2. Local prompting smoke conformance for the accepted profile.
3. Promotion-readiness regeneration when the profile is proposed for promotion.

No implementation may be reported complete with only imports, mocks, dry runs, or binary presence checks.

### LPCPP-11: Authority Updates

Any implementation that changes runtime behavior MUST update source-of-truth docs in the same change.

Required authority candidates:
1. `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/ROADMAP.md`
4. provider runtime target and provider truth artifacts
5. local prompting profile registry and conformance scripts
6. relevant operator or testing documentation if commands change

## Acceptance Criteria

Requirements acceptance is complete when:
1. this accepted requirements packet remains aligned with the requested first slice,
2. the exact first Qwen-family GGUF model file is selected,
3. first-slice model acquisition remains operator-managed,
4. an implementation plan can name one concrete first provider slice,
5. no requirement depends on unstated model files or unstated server state.

Provider implementation acceptance is complete only when:
1. `llama_cpp` is selectable as a first-class provider,
2. a real `llama-server` endpoint responds through the configured base URL,
3. one concrete GGUF model is resolved and identified,
4. strict JSON and tool-call smoke conformance pass on the real provider path,
5. promotion-readiness artifacts are regenerated before any promoted-profile claim,
6. unresolved gaps are reported as blockers rather than success.

## Open Decisions

1. Whether first-slice promotion will require rendered-prompt-byte auditing or continue under an accepted `message_payload_audited` waiver.

## First Target Model Record

The implementation plan MUST NOT be written around a placeholder model.
Before implementation planning, this record MUST be filled with exact non-placeholder values:

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

If the selected model is not sourced from Hugging Face, `repo_id` MUST record the exact local or upstream source used instead of a Hugging Face repo id.

## First Implementation Slice

The accepted first implementation slice is:
1. `llama_cpp` provider identity,
2. operator-managed `llama-server`,
3. configurable base URL,
4. configurable GGUF model root,
5. exactly one Qwen-family GGUF profile,
6. JSON-wrapper tool-call mode,
7. preflight against `/v1/models`,
8. strict JSON smoke,
9. tool-call smoke,
10. promotion-readiness regeneration before any promoted-profile claim.
