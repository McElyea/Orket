# llama.cpp Source Build Operator Note

Last updated: 2026-05-18
Status: Operator-reported local setup note (not Orket provider proof)
Owner: Orket Core
Related archived plan: `docs/projects/archive/local-provider-compatibility/2026-05-19-LLAMA-CPP-FIRST-SLICE-CLOSEOUT/LLAMA_CPP_PROVIDER_IMPLEMENTATION_PLAN.md`

## Authority Posture

This note records operator-provided local setup and smoke evidence for running a source-built llama.cpp server on the local Windows workstation.
It does not promote `llama_cpp` as an Orket provider, change runtime defaults, or satisfy the Orket live provider proof gates by itself.

The first-slice provider implementation still requires Orket-captured proof through the governed runtime path.

## Local Source Build Layout

1. Source checkout: `D:\llama.cpp-src`
2. Source build tree: `D:\llama.cpp-src\build-cuda-vs2022\`
3. Release fallback retained at: `D:\llama.cpp\b9204-cuda-13.1`
4. Target GGUF: `D:\Models\GGUF\Qwen3.6-27B-Q4_K_M.gguf`
5. Target model alias for the Orket lane: `qwen3.6-27b-q4_k_m`

The operator reported building CUDA llama.cpp from source with VS Build Tools 2022, CUDA 13.1, and RTX 4090 architecture `sm_89`.

## Helper Scripts

Launcher:

```powershell
powershell -ExecutionPolicy Bypass -File D:\llama.cpp-src\run-qwen36-27b-4090.ps1
```

Update and rebuild:

```powershell
powershell -ExecutionPolicy Bypass -File D:\llama.cpp-src\update-build-cuda.ps1
```

Helper files:
1. `D:\llama.cpp-src\run-qwen36-27b-4090.ps1`
2. `D:\llama.cpp-src\update-build-cuda.ps1`

## Default Qwen Launch Profile

The operator-reported practical launch profile uses:
1. `-ngl 99`
2. Flash Attention enabled
3. `32768` context
4. `f16` K-cache
5. `q8_0` V-cache
6. `--kv-unified`
7. `--no-mmap`
8. `16` threads
9. reasoning off for normal OpenAI-compatible responses

The tuning inputs were Reddit r/LocalLLaMA threads about RTX 4090 llama.cpp settings, Qwen 30B settings, Qwen 3.6 context settings, and KV-cache precision cautions.
Upstream llama.cpp CLI/help remains the flag authority.

## Operator-Reported Verification

Reported live proof:
1. Observed path: `primary`
2. Observed result: `success`
3. Source-built `llama-server.exe` detected `CUDA0: NVIDIA GeForce RTX 4090`.
4. The launcher script started the server and returned an OpenAI chat response: `script OK`.
5. The server loaded `D:\Models\GGUF\Qwen3.6-27B-Q4_K_M.gguf` with `32768` context successfully.

Reported Qwen3.6 27B Q4_K_M CUDA benchmark:
1. Prompt processing: `202.02 +/- 1.31 t/s`
2. Generation: `35.21 +/- 0.17 t/s`

## Not Verified In This Repo

1. Orket has not yet captured this as governed provider proof.
2. No Orket `llama_cpp` preflight, strict JSON smoke, tool-call smoke, or promotion-readiness regeneration has been run against this source-built server path.
3. `64k`, `100k`, and `200k` context were not tested.
4. Q5, Q6, Q8, and speculative decoding were not benchmarked.

## Remaining Drift Or Caveats

1. OpenSSL was not found during the source build, so HTTPS support inside `llama-server` is disabled.
2. The HTTPS limitation does not affect local `http://127.0.0.1:8080` serving for the first Orket slice.
3. The source checkout and helper scripts live outside this repository and are not tracked Orket files.
