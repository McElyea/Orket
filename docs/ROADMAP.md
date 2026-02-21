# Orket Roadmap

Last updated: 2026-02-21

## Outcome
Deliver production-ready quantization diagnostics on live Orket runs, then use those validated diagnostics to ship the next Orket experiment tools.

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

## Non-Negotiable Guardrails (All Work)
1. Pass/fail quality gates use Orket telemetry, not hardware sidecar metrics.
2. Invalid/polluted runs are excluded from KPI aggregates with no override.
3. `--include-invalid` may affect frontier/comparison views only.
4. Schema evolution is additive-only and backward compatible.
5. Every artifact must include `execution_lane` (`ci` | `lab`) and `vram_profile` (`safe` | `balanced` | `stress`).

## Execution Lanes
1. `ci` lane (mock-friendly):
   - Fast deterministic contract checks.
   - Parser/state-machine/schema/error-path coverage.
   - No hardware dependency.
2. `lab` lane (live hardware):
   - Thermal, VRAM, throughput, and variance physics.
   - Valid-run policy enforcement in real conditions.
   - Produces recommendation-grade evidence.

## VRAM Safety Profiles
1. `safe`: 50% cap (default for long experiment sessions).
2. `balanced`: 70-80% cap (representative everyday operation).
3. `stress`: 90-95% cap (boundary and cliff discovery).
4. Results are only comparable when profile + lane match.

## Now (Execute Immediately)
1. Finalize remaining telemetry contract hardening across providers.
Success criteria:
1. Providers emit only canonical token/timing states.
2. Streaming/non-streaming state transitions are consistent.
3. Adapter integration tests cover both paths.
4. All emitted artifacts include `execution_lane` and `vram_profile`.

2. Finish orchestration-overhead consistency guarantees.
Success criteria:
1. `internal_model_seconds` present on all success/failure paths.
2. `orchestration_overhead_ratio` present on all success/failure paths.
3. `run_quality_reasons` present on all success/failure paths.

3. Lock GPU sidecar parse policy as canonical.
Success criteria:
1. Required fields parsed as canonical snake_case keys.
2. Optional fields parsed when present; missing optionals never fail run execution.
3. `sidecar_parse_status` and `sidecar_parse_errors` emitted deterministically.

4. Enforce valid-run policy end-to-end.
Success criteria:
1. Invalid runs excluded from KPI aggregates always.
2. Invalid runs excluded from recommendation by default.
3. `--include-invalid` affects frontier/comparison visibility only.

## Next (After Now)
1. Add context sweep workflow policy defaults to matrix presets.
Deliverables:
1. Include recommended context profiles in benchmark config sets.
2. Align profile defaults with runbook safe/balanced/stress guidance.
3. Keep profile changes additive and backward compatible.

2. Add workflow-level explorer ingestion smoke check.
Deliverables:
1. Validate generated artifact index contains all required explorer kinds.
2. Fail workflow when schema version or provenance ref is missing in index rows.
3. Publish ingestion check output alongside artifact index.

## Later
1. Add thermal gate and cooldown policy checks for GPU sessions.
2. Add VRAM pre-flight guard rails (strict vs extended thresholds) as optional diagnostics.
3. Add sidecar schema spec files under `docs/specs/` for long-term contract governance.
4. Add VRAM fragmentation analyzer experiments.
5. Add model selector and adaptive routing prototypes after diagnostics evidence is stable.

## Idea Intake (Best Practice)
Use this format when adding ideas (in `Agents/Ideas.md`):
1. `Problem`: what is failing or unknown.
2. `Hypothesis`: what change should improve it.
3. `Scope`: affected files/components.
4. `Lane`: `ci`, `lab`, or both.
5. `Safety Profile`: `safe`, `balanced`, or `stress`.
6. `Success Metrics`: exact pass/fail thresholds.
7. `Go/No-Go`: explicit gate for merge/next-phase.
8. `Artifacts`: expected output files/fields.
