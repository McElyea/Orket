# llama.cpp First Slice Closeout

Last updated: 2026-05-19
Status: Closed first-slice implementation
Owner: Orket Core

## Scope Closed

This closeout retires the active `local-provider-compatibility` roadmap lane for the first llama.cpp Qwen GGUF slice.

Closed scope:
1. First-class `llama_cpp` requested provider token.
2. OpenAI-compatible transport reuse while preserving llama.cpp provider lineage.
3. Bounded GGUF inventory rooted at the configured model root.
4. `/v1/models` preflight for the target alias `qwen3.6-27b-q4_k_m`.
5. Deterministic profile resolution for `llama_cpp.qwen.chatml.v1`.
6. Non-streaming strict JSON and JSON-wrapper tool-call smoke proof on the real provider path.
7. Promotion-readiness regeneration with a truthful not-ready result.

## Proof Summary

Observed path: `primary`

Observed result: `partial success`

Live proof:
1. Started source-built `llama-server.exe` from `D:\llama.cpp-src\build-cuda-vs2022\bin\Release\llama-server.exe` with alias `qwen3.6-27b-q4_k_m`.
2. Server logs recorded CUDA device `NVIDIA GeForce RTX 4090`, model `D:\Models\GGUF\Qwen3.6-27B-Q4_K_M.gguf`, ChatML template initialization, and listening at `http://127.0.0.1:8080`.
3. `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider llama_cpp --model-id qwen3.6-27b-q4_k_m --timeout 15 --no-auto-load-local-model` passed with `OBSERVED_PATH=primary`, `OBSERVED_RESULT=success`, and `STREAMING_SMOKE=not_applicable`.
4. `ORKET_DISABLE_SANDBOX=1 python scripts/protocol/run_local_prompting_conformance.py --provider llama_cpp --model qwen3.6-27b-q4_k_m --suite smoke --strict-json-cases 1 --tool-call-cases 1 --strict --no-sanitize-model-cache --out-root benchmarks/results/protocol/local_prompting/llama_cpp_first_slice_2026-05-19` passed.
5. Strict JSON smoke: `1/1` passed.
6. Tool-call smoke: `1/1` passed.
7. Promotion-readiness output at `benchmarks/results/protocol/local_prompting/llama_cpp_first_slice_2026-05-19/promotion_decision/local_prompting_promotion_readiness.json` records `ready=false`.

Structural proof:
1. Provider identity, quarantine, GGUF inventory, profile resolution, request-shape telemetry, preflight behavior, provider truth, runtime config ownership, and conformance-script support are covered by focused contract/unit tests.
2. Docs project hygiene passed.
3. Runtime truth drift check passed.

## Promotion State

`llama_cpp` is implemented but not promoted.

Promotion remains blocked by:
1. Promotion corpus volume: only smoke proof exists, not `1000` strict JSON and `500` tool-call cases.
2. Template audit or explicit accepted waiver is missing for the ChatML profile.
3. Local SHA256 digest for the GGUF remains `pending`; the file is present with size `16817244384`.

These blockers do not reopen the first-slice implementation lane. They require a later explicit promotion-readiness or promotion-hardening lane.

## Archived Authority

The active lane files are archived in this folder:
1. `LLAMA_CPP_PROVIDER_IMPLEMENTATION_PLAN.md`
2. `LLAMA_CPP_PROVIDER_REQUIREMENTS.md`
3. `LLAMA_CPP_SOURCE_BUILD_OPERATOR_NOTE.md`
4. `llama_cpp_first_target_model_source_verification_2026-05-18.json`

