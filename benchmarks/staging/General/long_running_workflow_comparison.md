# Long-running workflow comparison

Recorded on October 4, 2026, on native Windows. The installed core/SDK pair is 0.7.2/0.7.2; main is 17fe469cf71294a03d8d8b9cb5a37cb7735aedd7. Real-model calls use the existing llama.cpp server and `orcarouter_qwen3.8-27b-uncensored-q4_k_l`.

## What changed

Ran the retained long-run benchmark entrypoints and staged this comparison. Fixed the demonstrated `run_stream_scenario.py` harness blocker by entering and exiting the real API lifespan around session and WebSocket traffic. Before the fix, the first request returned 503 “API runtime is not ready.” The candidate bytes used for the live reruns exactly match the repository correction. Added three integration cases covering startup, scenario results and shutdown. No runtime package or provider setting changed.

## What was verified

### Native deterministic review execution

| Scenario | Repetitions | Batch wall seconds | Result |
| --- | ---: | ---: | --- |
| constants_flags | 1000 | 213.095 | Pass; strict replay parity |
| secrets_sha1 | 1000 | 243.960 | Pass; strict replay parity |
| auth_insecure | 1000 | 275.518 | Pass; strict replay parity |
| math_parse_int | 1000 | 228.059 | Pass; strict replay parity |
| truncation_bounds | 100 | 23.765 | Pass; strict replay parity |

**4,100 repetitions passed**, plus the runners’ setup/strict/replay controls. All five persisted reports passed their canonical validators. These are real native filesystem/Git/review executions using the deterministic lane, with no LLM calls. Times include native process startup and control runs; they are not per-task model timings. The retained historical review reports prove counts but lack comparable wall timings.

### Live streaming

One complete six-scenario gate passed in **25.438 seconds** after the API lifespan correction and after the server became idle. The real-model success scenarios emitted actual nonempty tokens. The subsequent **1,000-loop request failed fast in loop 6 after 148.040 seconds**: five complete loops passed, with 33 passing and one failing scenario verdict overall. The sixth happy-path scenario emitted no token delta and committed `fail_closed` after approximately 10 seconds. Its canonical validator rejected the incomplete endurance run. No threshold or timeout was relaxed.

A separate local request timed out after 30.172 seconds. The operator server’s single slot was observed busy and later idle. That observation does not establish the cause of every failure. Existing saved `live_1000_consistency.json` and Ollama reports each actually completed **one** loop, in 6.627 and 11.344 seconds respectively; the name is not evidence of 1,000 completed loops. Different providers, models and runtime versions prevent a model-speed comparison. The three API controls are in-process TestClient integration proof; the provider scenarios make real HTTP calls to llama.cpp.

### Service load and stub soak

The saved baseline and heavy profile sizes produced **6,040 transport samples**, with zero request/connection failures in the load reports. Services ran only on task-owned ports 18082 and 18083. **This does not prove completed card work:** 240 synthetic trigger requests were accepted, and the service log contains 40 `CardNotFound` background-task tracebacks for `LOAD-EPIC-*`. The other accepted triggers have no completion claim. The old load harness measures admission and connection handling.

| Profile / metric | Historical p50 ms | Current p50 ms |
| --- | ---: | ---: |
| baseline / webhook | 33.553 | 99.135 |
| baseline / api_heartbeat | 40.661 | 155.041 |
| baseline / parallel_epic_trigger | 17.641 | 71.366 |
| baseline / websocket_connect | 139.580 | 200.654 |
| heavy / webhook | 87.308 | 208.337 |
| heavy / api_heartbeat | 237.240 | 520.942 |
| heavy / parallel_epic_trigger | 106.610 | 263.967 |
| heavy / websocket_connect | 412.741 | 1742.701 |

These are observational transport timings. ReviewRun CPU/disk work overlapped the new profiles; historical machine/load equivalence is not established. They are not an isolated regression measurement.

The canonical **120-turn stub-provider soak passed** all three event/terminal checks in 1.454 command-wall seconds. This is structural provider-contract proof, not live model endurance. Five targeted integration/identity tests passed. New-test lint and `git diff --check` passed.

## What was not verified

A completed 1,000-loop live streaming run, old-model/quant comparisons, actual cold reload, thermal endurance, non-Windows behavior and successful card execution from the service load test remain unverified. The thermal profiler summarizes existing sweeps rather than launching a live soak.

The archived 30-page/28-code-file 1,000-run benchmark was attempted using a copy of its retained fixture and matching historical policy. It completed zero runs: the retained `.git` directory lacks `HEAD`, and Git reports that the copied fixture is not a repository. The original fixture and report were preserved.

## Remaining blockers or drift

- Streaming endurance stops at the demonstrated no-token/provider failure. A successful short retry does not close it.
- Synthetic service triggers lack real cards and produce unobserved background-task errors despite HTTP 200.
- The 30-page benchmark needs its historical Git fixture restored before an equivalent rerun.
- The streaming script retains five pre-existing lint findings: three E402 bootstrap imports and two SIM102 conditions. The correction does not widen them. Its existing oversized function/file was not enlarged.

## Evidence and preservation

Exact argv, native Windows job receipts, stdout/stderr and failed attempts are retained under `.tmp/longrun-comparison/`. Isolated projects and per-iteration review/stream artifacts remain at `C:\Source\Orket-longrun-comparison`. The sibling JSON links and hashes the receipts, historical inputs and changed source. `.tmp/longrun-comparison/file_inventory.json` enumerates local helpers/evidence and external files. All task-owned processes settled; service ports were released. The operator board, skip-worktree flag, selected model/template, original server PID/start time and other worktrees were preserved.

The October 6, 2026 00:00 America/Denver cutoff and final six-hour reserve remain unchanged. PRR remains closed, with PRR-S1 and broader architectural debt deferred. No release or benchmark promotion was made; the edits and staging artifacts remain uncommitted.

## Exact repository files touched

- `scripts/streaming/run_stream_scenario.py`
- `tests/scripts/test_stream_scenario_lifespan.py`
- `scripts/README.md`
- `benchmarks/staging/General/long_running_workflow_comparison.json`
- `benchmarks/staging/General/long_running_workflow_comparison.md`
- `benchmarks/staging/index.json`
- `benchmarks/staging/README.md`
