# Protocol-Governed LM Studio Findings and Live Test Plan (v1)

Last updated: 2026-03-06  
Status: Archived (historical findings and test plan)  
Owner: Orket Core

References:
1. `docs/internal/LMStudioData.txt`
2. `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
3. `docs/projects/archive/protocol-governed/PG03062026/local-prompting-plan.md`
4. `docs/CONTRIBUTOR.md`

## 1. Purpose

Document validated LM Studio run findings from `docs/internal/LMStudioData.txt`, adopt the strongest corrective suggestions, and define a live-test-heavy remediation plan before any LM Studio promotion decision.

## 1a. Execution Update (2026-03-05)

Completed implementation slices:
1. Phase A baseline tooling landed:
   - `scripts/protocol/analyze_lmstudio_log_capture.py`
   - `tests/scripts/test_analyze_lmstudio_log_capture.py`
2. Phase B session-control surface landed:
   - `lmstudio_session_mode` (`none|context|fixed`)
   - `lmstudio_session_id` (optional fixed value)
   - policy + conformance telemetry wiring for session mode/id-presence
3. Live conformance runs executed (real LM Studio endpoint):
   - `none/qualification_200`: strict JSON `200/200`, tool-call `200/200`, anti-meta chatter/fence `0.0/0.0`
   - `context/qualification_200`: strict JSON `200/200`, tool-call `200/200`, anti-meta chatter/fence `0.0/0.0`
   - `fixed/qualification_80`: strict JSON `80/80`, tool-call `80/80`, anti-meta chatter/fence `0.0/0.0`
4. Failure summaries generated for the three runs above:
   - `none/qualification_200/failure_summary.json`
   - `context/qualification_200/failure_summary.json`
   - `fixed/qualification_80/failure_summary.json`
5. LM Studio live server-log snapshot analyzed:
   - `benchmarks/results/protocol/local_prompting/lmstudio_cache_study/live_log_snapshot_2026-03-05_1809/analysis/lmstudio_cache_metrics.json`

Current execution decision:
1. Continue promotion-scale campaigns on `none` and `context`.
2. Keep `fixed` as reduced-volume diagnostic coverage until runtime stability is consistently proven at higher volumes.

## 2. Evidence Snapshot (From `LMStudioData.txt`)

Observed facts:
1. Repeated state selection uses `session_id=<empty>` in LM Studio slot selection logs.
2. Repeated cache/path churn markers appear:
   - `failed to truncate tokens ... clearing the memory`
   - `forcing full prompt re-processing due to lack of cache data`
   - `cache reuse is not supported - ignoring n_cache_reuse = 256`
3. Strict deterministic payload success is repeatedly present in conformance-shaped requests:
   - strict JSON payloads
   - strict tool-call-shaped JSON payloads
4. Lifecycle volatility is present:
   - model TTL unload events
   - at least one client disconnect + operation canceled load attempt
5. The file contains both raw runtime logs and later narrative critic commentary in one artifact.

## 3. Findings to Carry Forward

### 3.1 Strong Suggestions (Adopt)

1. Add explicit session continuity controls for LM Studio/OpenAI-compatible calls so cache behavior can be tested intentionally instead of always running with empty session identity.
2. Keep deterministic strict sampling defaults (`temperature=0`, fixed seed where supported, stable stop set, bounded output) for protocol conformance paths.

### 3.2 Medium Findings (Address)

1. Current LM Studio evidence indicates unstable cache reuse and recurrent full prompt re-processing across repeated calls.
2. Startup/load lifecycle churn (TTL unload + warmup cancellation event) can distort runtime latency and reliability signals.

### 3.3 Low Findings (Address)

1. `max_tokens=1` "Continue." loops are useful smoke checks but weak evidence for strict protocol quality under realistic payload lengths.
2. Mixed raw logs + narrative commentary in one file reduces auditability and makes machine analysis less reliable.

## 4. Remediation Strategy

### Phase A: Evidence Hygiene and Baseline

Tasks:
1. Split future evidence into:
   - raw LM Studio server log capture
   - derived analysis summary
2. Standardize canonical artifacts under:
   - `benchmarks/results/protocol/local_prompting/lmstudio_cache_study/`
3. Add deterministic metric extraction for:
   - `session_id=<empty>` count
   - full reprocess count
   - failed truncate count
   - prompt eval timing distribution
   - finish reason distribution

Exit criteria:
1. Raw and derived evidence are separated.
2. Baseline metrics are reproducible from a single command path.

### Phase B: Session Continuity Control Surface

Tasks:
1. Add runtime control for LM Studio session mode in OpenAI-compatible path (candidate keys):
   - `lmstudio_session_mode`: `none|context|fixed`
   - `lmstudio_session_id`: optional fixed value
2. Wire control into payload only when provider path is LM Studio.
3. Add telemetry fields:
   - `lmstudio_session_mode`
   - `lmstudio_session_id_present` (boolean only, no sensitive value leakage)
4. Add unit tests to verify payload and telemetry behavior by mode.

Exit criteria:
1. Session mode is explicitly testable and observable.
2. Default behavior remains backward-compatible (`none`).

### Phase C: Live A/B Cache Stability Campaign (High Volume)

Campaign matrix:
1. Session mode:
   - `none` (baseline)
   - `context` (use runtime session id)
   - `fixed` (single fixed session id for test run)
2. Task class:
   - `strict_json`
   - `tool_call`
3. Case volume tiers:
   - smoke: `20` per task class
   - qualification: `200` per task class
   - promotion: `1000 strict_json`, `500 tool_call`

Required live runs:
1. Run each session mode through smoke and qualification tiers.
2. Run promotion tier on best two modes only.
3. For each run, capture:
   - strict reports
   - anti-meta report
   - suite manifest
   - extracted LM Studio cache metrics

Exit criteria:
1. Best mode shows reduced cache churn indicators versus baseline.
2. Conformance rates remain at or above configured thresholds.
3. No new regressions in strict validators or anti-meta rates.

### Phase D: Multi-Turn and Repair Stress

Tasks:
1. Add live two-turn and three-turn strict workflows:
   - valid strict response
   - forced invalid response
   - deterministic repair response
2. Include large-schema variants and longer prompt bodies.
3. Compare session modes for repair convergence and latency tails.

Exit criteria:
1. Deterministic repair behavior remains bounded and stable in multi-turn paths.
2. Selected session mode does not regress LP-09/LP-10 behavior.

## 5. Live Test Command Plan

Preflight:
1. `python scripts/providers/check_model_provider_preflight.py --provider lmstudio --auto-select-model --timeout 5 --smoke-stream`

Smoke conformance (all session modes):
1. `python scripts/protocol/run_local_prompting_conformance.py --provider lmstudio --model qwen3.5-4b --cases 20 --strict --lmstudio-session-mode <none|context|fixed> --lmstudio-session-id <id_for_context_or_fixed> --out-root benchmarks/results/protocol/local_prompting/lmstudio_cache_study/<mode>/smoke`

Qualification conformance:
1. `python scripts/protocol/run_local_prompting_conformance.py --provider lmstudio --model qwen3.5-4b --strict-json-cases 200 --tool-call-cases 200 --strict --lmstudio-session-mode <none|context> --lmstudio-session-id <id_for_context> --out-root benchmarks/results/protocol/local_prompting/lmstudio_cache_study/<mode>/qualification_200`
2. `python scripts/protocol/run_local_prompting_conformance.py --provider lmstudio --model qwen3.5-4b --strict-json-cases 80 --tool-call-cases 80 --strict --lmstudio-session-mode fixed --lmstudio-session-id <fixed_id> --out-root benchmarks/results/protocol/local_prompting/lmstudio_cache_study/fixed/qualification_80`

Promotion conformance (top modes):
1. `python scripts/protocol/run_local_prompting_conformance.py --provider lmstudio --model qwen3.5-4b --suite promotion --strict --lmstudio-session-mode <best_mode> --lmstudio-session-id <id_if_needed> --out-root benchmarks/results/protocol/local_prompting/lmstudio_cache_study/<mode>/promotion`

Failure aggregation:
1. `python scripts/protocol/summarize_local_prompting_failures.py --input <strict_json_report> --input <tool_call_report> --out <failure_summary> --strict`

Drift gate:
1. `python scripts/protocol/compare_local_prompting_profile_drift.py --before <baseline_registry_snapshot> --after model/core/contracts/local_prompt_profiles.json --out <profile_delta_report> --strict`

Template audit:
1. `python scripts/protocol/audit_prompt_templates.py --registry model/core/contracts/local_prompt_profiles.json --out-root benchmarks/results/protocol/local_prompting/lmstudio_cache_study --strict`

## 6. Promotion Gate Additions for LM Studio

Additional required gates for LM Studio promotion:
1. Cache churn metrics must improve versus `session_mode=none` baseline:
   - lower `failed_truncate_count`
   - lower `full_reprocess_count`
2. No regression in conformance:
   - strict JSON threshold met
   - tool-call threshold met
   - anti-meta thresholds met
3. Multi-turn repair stress campaign must pass deterministic retry bounds.

## 7. Open Questions

1. Confirm exact OpenAI-compatible field name(s) LM Studio honors for sticky session identity in current deployed version.
2. Confirm whether any cache-affinity header is officially supported and stable for this path.
3. Decide whether TTL unload policy should be tuned during promotion campaigns to reduce warmup noise.
4. Confirm whether current LM Studio runtime exposes a supported toggle equivalent to llama.cpp "no context shift" for SWA/hybrid/recurrent architectures.

## 8. External Suggestion Triage (2026-03-05)

Validated from live logs/API:
1. Cache pressure diagnosis is valid.
   - observed peaks include `cache state: 156 prompts` and near-limit memory occupancy against `8192 MiB`.
2. Recurrent full reprocessing diagnosis is valid.
   - repeated `forcing full prompt re-processing due to lack of cache data`.
3. Session affinity concern is valid.
   - slot selection repeatedly shows `session_id=<empty>`, including runs where payloads include a `session_id` field.
4. Slot fanout concern is valid for this workload.
   - load logs show `n_slots = 4` while most conformance traffic is serialized through a single active slot.

Accepted operational actions:
1. Prefer `n_slots=1` (Parallel 1) for serialized strict conformance campaigns.
2. Use periodic model eject/reload between long campaigns to clear high-fragmentation cache state.
3. Keep deterministic strict sampling/profile policy as currently implemented.
4. Continue `none/context` as promotion candidates; keep `fixed` in reduced-volume diagnostic lane until stability is consistently proven.

Rejected or unproven recommendations:
1. `POST /v1/internal/model/unload` is not supported on this instance (`Unexpected endpoint or method`).
2. `x-slot-id` header is not a verified control surface for stable slot pinning in current runs.
3. Hard-coding `n_keep` in provider code is not recommended:
   - `n_keep` is prompt-shape dependent and already varies by workload/profile,
   - forcing a static value risks mismatches when prompt prefix changes.

## 9. SWA Reprocess Interpretation (Consult Notes, 2026-03-06)

Operational interpretation:
1. `forcing full prompt re-processing due to lack of cache data` is currently consistent with llama.cpp fallback behavior for SWA/hybrid/recurrent memory when context-shifted reuse is not viable.
2. In this state, KV reuse is effectively reduced and prompt tokens are re-evaluated more often, which can look like "fast but repetitive" server activity in logs.
3. This is not a strict-JSON correctness failure by itself; it is a runtime efficiency/stability issue.

Immediate operating posture:
1. Keep test batches short and explicit (`5+5`, `20+20`) and only scale after each batch confirms:
   - strict/tool pass rates at target,
   - no runaway cache churn trend.
2. Prefer `Parallel=1` for serialized protocol runs.
3. Eject/reload between medium or large batches to reset fragmented cache state.
4. Keep `context_length` bounded (`4096` currently loaded) for this campaign until churn is controlled.

Chunked live-test cadence (anti-spin):
1. Step A: `5+5` context smoke.
2. Step B: `20+20` none and context.
3. Step C: `80+80` only for mode that is stable in Step B.
4. Step D: promotion volume only after Step C passes and cache churn remains bounded in captured logs.

## 10. Cache Sanitation Protocol (2026-03-06)

Policy:
1. LM Studio protocol run scripts must clear loaded model instances at run start and run end by default.
2. This sanitation is now wired into:
   - `scripts/providers/check_model_provider_preflight.py` when `--provider lmstudio`
   - `scripts/protocol/run_local_prompting_conformance.py` when `--provider lmstudio`
3. Opt-out is explicit only:
   - `--no-sanitize-model-cache`

Rationale:
1. Enforces a deterministic baseline and prevents silent carry-over of fragmented KV state between campaigns.
2. Aligns with observed cache-thrashing behavior in `docs/internal/LMStudioData.txt`.

Implementation note:
1. Use only documented LM Studio API surfaces observed in this environment (`/api/v1/models`, `/api/v1/models/load`, `/v1/*` OpenAI-compatible endpoints) for automation.
