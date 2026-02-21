# Orket Roadmap

Last updated: 2026-02-21

## Outcome
Deliver production-ready quantization diagnostics on live Orket runs with strict telemetry, valid-run enforcement, and reproducible recommendations.

## How To Read This
This is a forward-only execution plan.
1. `Now`: current implementation targets.
2. `Next`: immediate follow-on once `Now` is complete.
3. `Later`: lower-priority work after core correctness and operations are stable.

History is in git, not this file.

## Roadmap Hygiene Rule
After every 5 completed roadmap items:
1. Remove completed items from this file.
2. Promote `Next` items into `Now`.
3. Add new `Later` items.
4. Update `Last updated`.

## Non-Negotiable Guardrails
1. Pass/fail quality gates use Orket telemetry, not hardware sidecar metrics.
2. Invalid/polluted runs are excluded from KPI aggregates with no override.
3. `--include-invalid` may affect frontier/comparison views only.
4. Schema evolution is additive-only and backward compatible.

## Now (Execute Immediately)
1. Finalize telemetry contract across providers.
Success criteria:
1. Providers emit only canonical token/timing states.
2. Streaming/non-streaming state transitions are consistent.
3. Adapter integration tests cover both paths.

2. Harden orchestration-overhead contract.
Success criteria:
1. `internal_model_seconds` emitted on all success/failure paths.
2. `orchestration_overhead_ratio` emitted on all success/failure paths.
3. Run-quality reason fields are always present.

3. Implement canonical GPU sidecar parse contract.
Success criteria:
1. Required sidecar fields parsed into canonical snake_case keys.
2. Optional sidecar fields parsed when available without failing run.
3. Sidecar block emits:
   - `sidecar_parse_status`
   - `sidecar_parse_errors`

4. Enforce valid-run policy in summary logic.
Success criteria:
1. Invalid runs excluded from KPI aggregates always.
2. Invalid runs excluded from recommendation by default.
3. `--include-invalid` only affects frontier/comparison visibility.

## Next (After Now)
1. Add visualization/reporting script for operator review.
Deliverables:
1. Generate TPS vs adherence scatter from `sweep_summary.json`.
2. Annotate minimum-viable and best-value quant frontier points.
3. Consume validated rows only by default.

2. Expand E2E regression matrix for policy interactions.
Deliverables:
1. Cover sidecar parsing + KPI gating + invalid-run inclusion interactions.
2. Add regression fixtures for `sidecar_parse_status` error states.
3. Enforce no schema drift in CI contract tests.

3. Add structured GPU profile variants for sidecar templates.
Deliverables:
1. Define backend/vendor profile presets (NVIDIA/AMD/CPU-only).
2. Keep canonical sidecar schema stable across profiles.
3. Add profile compatibility notes to runbook.

## Later
1. Add thermal gate and cooldown policy checks for GPU sessions.
2. Add VRAM pre-flight guard rails (strict vs extended thresholds) as optional diagnostics.
3. Add sidecar schema spec files under `docs/specs/` for long-term contract governance.
