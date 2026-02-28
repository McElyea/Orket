# 03 - Model Streaming Integration Plan (v1)

## Objective
Integrate real local model streaming into Orket while preserving:
- Interaction Plane streaming (non-authoritative)
- Authority Plane deterministic commits at explicit boundaries
- Existing stream laws (seq ordering, dropped ranges, terminality, cancel semantics)

## Baseline Freeze (Harness)
- Tag current stream scenario harness as stable:
  - scenarios: `s0_unknown_workload_400`, `s5_backpressure_drop_ranges`, `s6_finalize_cancel_noop`
  - verdict schema: `stream_verdict_v1`
- CI: add job that runs `s0/s5/s6` and fails on any non-PASS.
- No further harness feature changes unless required for model integration.

## Model Provider Seam

### Contract
Introduce `ModelStreamProvider` as a runtime seam that produces provider lifecycle events for a turn.

#### Provider responsibilities
- Execute model selection/loading
- Stream output chunks/tokens
- Support cancellation

#### Provider must not:
- mutate authoritative state
- assign Orket seq numbers
- emit Orket StreamEvents directly

### Minimum interface (v1)
- `start_turn(req) -> AsyncIterator[ProviderEvent]`
- `cancel(provider_turn_id) -> None`
- Optional:
  - `health()`
  - `prewarm(model_id)`

### ProviderEvent (v1)
Required fields:
- `provider_turn_id` (opaque stable id)
- `event_type`: `selected | loading | ready | token_delta | stopped | error`
- `payload` (event-specific)
Optional:
- `mono_ts_ms` (provider-local diagnostic only)

## Runtime Mapping to Canonical Stream Events
- Orket runtime maps `ProviderEvent -> StreamEvent`:
  - `selected -> model_selected`
  - `loading  -> model_loading`
  - `ready    -> model_ready`
  - `token_delta -> token_delta`
  - `stopped/error -> turn_final or turn_interrupted` (per cancel/stop_reason)
- All seq allocation, drop/coalesce, and `dropped_seq_ranges` remain in `StreamBus` only.
- WebSocket adapter remains pass-through.

## Interaction Execution Wiring
- Add a built-in workload (or mode) that uses `ModelStreamProvider` for generation.
- Authority boundary remains unchanged:
  - streamed tokens never mutate world truth
  - `turn_final` then `commit_final` via existing finalize/commit path

## Cancellation Semantics
- `InteractionContext.cancel -> provider.cancel(provider_turn_id)`
- Laws enforced:
  - exactly one terminal interaction event per turn (`turn_final xor turn_interrupted`)
  - no post-terminal events except `commit_final`
  - cancel-after-final is noop (verified by `s6`)

## Latency + Warm Hooks
- Emit `model_loading` immediately once selection begins.
- Measure and record latency metrics in observed artifacts:
  - input -> `turn_accepted`
  - `model_selected` -> `model_loading`
  - `model_loading` -> `model_ready`
  - `model_ready` -> first `token_delta`
- Optional warm hooks (`prewarm`) added with no policy logic in v1.

## Real Provider Adapter (v1)
- Implement first real provider for chosen local runtime (for example, Ollama or llama.cpp server).
- Provider translates underlying stream chunks to `ProviderEvent.token_delta`.
- Provider emits `selected/loading/ready` deterministically from its own state transitions.

## New Live Scenarios (Provider-enabled only)
- `s7_real_model_happy_path`
- `s8_real_model_cancel_mid_gen`
- `s9_real_model_cold_load_visibility`

Note:
- `s0/s5/s6` remain baseline regression scenarios and must be green regardless of provider availability.

## Rollout Controls
- Feature flag: `ORKET_MODEL_STREAM_PROVIDER = stub | real`
- Default: `stub` in CI
- Local/dev: `real`
- Fail-fast diagnostics when real provider unavailable:
  - clear HTTP 4xx/5xx response for `start_turn` failures
  - no async fail-closed turns due to missing provider

## Acceptance Gate
Required green:
- Baseline harness: `s0/s5/s6`
- Provider scenarios: `s7/s8/s9` when provider enabled
- No stream law regressions
- Deterministic authority artifacts unchanged

## Phase 1 Implementation Slice
Smallest slice that proves the seam:
1. Add `ModelStreamProvider` + `ProviderEvent` types + stub provider wrapping current `stream_test` behavior.
2. Wire runtime to use provider in a new built-in workload mode.
3. Keep `s0/s5/s6` green.
4. Add `s7` using the stub provider (validate provider-path without external dependencies).

Phase 2:
1. Implement real adapter (`Ollama`/`llama.cpp`/`vLLM`).
