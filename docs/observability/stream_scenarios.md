# Stream Scenarios

This document defines how to run live stream scenarios and what they prove.

## Runtime and Transport
- Canonical publisher/subscriber: in-proc stream bus.
- External transport under test: WebSocket.
- WebSocket adapter forwards canonical bus events without mutating ordering or payloads.

## Run a Scenario
```powershell
python scripts/run_stream_scenario.py --scenario <scenario-yaml-path> --timeout 20
```

## Run Full Model-Streaming Gate
```powershell
python scripts/run_model_streaming_gate.py --provider-mode stub --timeout 20
```
```powershell
python scripts/run_model_streaming_gate.py --provider-mode real --timeout 20
```

## Real Provider Preflight
```powershell
python scripts/check_model_provider_preflight.py
```
```powershell
python scripts/check_model_provider_preflight.py --smoke-stream
```

## Provider Identity In Verdicts
- `verdict.json -> observed` now includes:
  - `provider_mode`
  - `provider_name`
  - `provider_model_id`
  - `provider_base_url`

## PASS/FAIL Meaning
- `PASS`: stream laws hold and scenario expectations hold.
- `FAIL`: either a stream law violation or a scenario expectation violation.
- Verdict artifact path is printed at run end (`verdict.json` plus `events.jsonl`).
- `require_commit_final` defaults to `false`; scenarios that validate authority completion should set `require_commit_final: true`.

## Dropped Range Convention (v1)
- When best-effort drops occur, runtime surfaces `dropped_seq_ranges` on the next emitted event for the same turn, and at latest on the terminal interaction event.

## Scenario Matrix
| Scenario | Purpose | Primary Laws |
|---|---|---|
| `s0_unknown_workload_400` | API fail-fast for unknown workload IDs (no async turn side effects) | API contract + no-stream side effect assertion |
| `s5_backpressure_drop_ranges` | Backpressure cap + dropped ranges surfaced + must-deliver terminal event (and commit if emitted) | `R0`, `R9b` |
| `s6_finalize_cancel_noop` | Cancel after `commit_final` is a noop: no further events and no terminal-state reopening | `R3`, `R1b` |
| `s7_real_model_happy_path` | Provider seam happy-path with `model_stream_v1` and `ORKET_MODEL_STREAM_PROVIDER=stub` | Provider-event mapping + terminal/commit flow |
| `s8_real_model_cancel_mid_gen` | Provider seam cancel behavior on `model_stream_v1` (`stub`) before first token emission | Cancel semantics + terminality |
| `s9_real_model_cold_load_visibility` | Provider seam cold-load visibility on `model_stream_v1` (`stub` with `force_cold_model_load`) | Model loading/ready sequencing |

## Notes
- `s5_backpressure_drop_ranges` validates stream semantics and does not require `commit_outcome=ok`; it accepts `outcome: any`.
- `s5_backpressure_drop_ranges` requires a minimum number of `token_delta` events and observed `dropped_seq_ranges` to ensure real backpressure was exercised.
- `s5_backpressure_drop_ranges` may additionally enforce `min_dropped_seq_ranges_count` to prove at least one drop range surfaced.
