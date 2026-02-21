# Orket Roadmap

Last updated: 2026-02-21

## Outcome
Deliver production-ready quantization testing on live Orket runs, with strict telemetry, deterministic summaries, and actionable quant recommendations per hardware fingerprint.

## Roadmap Maintenance Protocol
1. This roadmap is forward-only. Do not keep completed-history lists here.
2. Each item must include `status: pending | in_progress | completed`.
3. Keep counter `completed_since_last_roadmap_update`.
4. On each completion, increment the counter by `1`.
5. If `completed_since_last_roadmap_update >= 5`, update roadmap in the same change set:
   - Remove all `status: completed` items.
   - Add/refresh next pending items.
   - Reset `completed_since_last_roadmap_update = 0`.
6. Source of truth for historical completion is git history.

## Runtime State
1. `completed_since_last_roadmap_update = 1`

## Active Work Items
1. status: `pending`
   item: Add provider-capability integration tests for streaming/non-streaming adapters to validate `init_latency` and token status transitions.
2. status: `pending`
   item: Add additional matrix presets (logic-only, refactor-heavy, mixed) in `benchmarks/configs/`.
3. status: `pending`
   item: Add self-hosted full quant sweep workflow (manual dispatch) for real model execution and artifact upload.
4. status: `pending`
   item: Integrate KPI policy checker into self-hosted full quant sweep workflow path (real sweep summary artifacts, not sample payloads).
5. status: `pending`
   item: Add baseline retention automation policy doc + command examples for periodic prune by age/count.
6. status: `pending`
   item: Add structured sidecar parser mode for llama-bench native output and map parsed metrics into summary-sidecar block.

## Guardrails
1. Keep pass/fail quality gates based on Orket telemetry, not hardware sidecar metrics.
2. Keep polluted-run exclusion default for frontier logic.
3. Keep summary schema backward-compatible when adding fields.
