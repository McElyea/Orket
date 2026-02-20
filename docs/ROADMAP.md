# Orket Roadmap

Last updated: 2026-02-19

## Goal
Add telemetry collection to the existing execution loop so each test run reports performance and instruction-following quality in addition to outcome, without refactoring core engine behavior.

## Scope
1. Extend result reporting with telemetry fields.
2. Capture generation latency and memory usage around model calls.
3. Add constraint validation (regex + AST) and score adherence.
4. Emit root report metadata needed for downstream consumers.
5. Preserve existing test execution and gate logic semantics.

## Out of Scope
1. Rewriting engine orchestration.
2. Changing pass/fail decision criteria.
3. UI/dashboard redesign.
4. Provider protocol rewrites beyond stream capability detection.

## Delivery Plan

### Phase 1: Contract and Data Model
1. Define canonical report shape in code-level types:
   - Root: `schema_version`, `report_generated_at`, `test_runs`.
   - Per run: `test_id`, `outcome`, `telemetry`.
   - Telemetry: `init_latency`, `total_latency`, `peak_memory_rss`, `adherence_score`.
2. Add explicit nullability rules:
   - `init_latency` is null when true token streaming is unavailable.
   - `adherence_score` is null when code is not produced.
3. Add deterministic float formatting utility (3 decimal places) used by all telemetry outputs.
4. Ensure report consumers ignore unknown telemetry fields for forward compatibility.

Exit criteria:
1. Report writer produces the new shape for a sample run.
2. Existing consumers continue to parse reports without failures.

### Phase 2: Telemetry Instrumentation Around Generation
1. Wrap generation call with timing instrumentation using `time.perf_counter()`:
   - Start at request dispatch.
   - End at full response completion or failure.
2. Implement stream-aware first-byte capture:
   - If provider emits true token stream callbacks, set `init_latency` at first token/chunk event.
   - Otherwise set `init_latency` to null.
3. Capture peak RSS during generation window using `psutil`.
4. Use `try/finally` to guarantee telemetry collection on success, fail, or exception.
5. Keep instrumentation passive: no changes to existing scoring/outcome logic.

Exit criteria:
1. `total_latency` and `peak_memory_rss` are always present.
2. `init_latency` behavior matches stream capability rules.
3. Error paths still emit telemetry payload.

### Phase 3: Constraint Validation and Adherence Scoring
1. Add `ConstraintValidator` module with two tiers:
   - Regex checks for forbidden/required patterns.
   - AST checks for structural requirements.
2. Define rule primitives:
   - `required_function_name`
   - `argument_count`
   - `return_type_annotation`
3. Compute adherence as `passed_checks / total_checks`.
4. Default adherence to `1.000` when no checks are configured.
5. Set adherence to null when no code payload exists to validate.

Exit criteria:
1. Validator returns stable scores across repeated runs with same input.
2. Invalid code snippets fail AST checks deterministically.

### Phase 4: Report Assembly and Integration
1. Update result aggregation to include telemetry per test run.
2. Add `report_generated_at` in UTC ISO-8601 at report write time.
3. Ensure all telemetry floats are rounded consistently to 3 decimals.
4. Validate schema emission in both normal and failure-heavy suites.

Exit criteria:
1. Final `orket_report.json` includes required root and per-run telemetry fields.
2. Rounding/formatting is consistent across platforms.

### Phase 5: Verification and Hardening
1. Add unit tests:
   - Timing utility behavior.
   - Memory sampler peak tracking.
   - Regex and AST validator scoring.
   - Float rounding utility.
2. Add integration tests:
   - Streaming provider path (`init_latency` set).
   - Non-streaming provider path (`init_latency` null).
   - Generation failure path (telemetry still emitted, score null).
3. Add regression tests to verify no behavior changes in existing pass/fail flow.
4. Run full test suite and determinism gates.

Exit criteria:
1. New tests pass locally and in CI.
2. Existing benchmark and policy gates remain green.

## Implementation Notes
1. Keep telemetry capture isolated behind helper utilities to avoid spreading instrumentation concerns across execution code.
2. Prefer additive changes to existing result classes/interfaces.
3. Keep provider capability checks explicit and conservative; do not infer streaming from response content.
4. Record memory as absolute RSS peak during generation window, not system-wide memory.

## Risks and Mitigations
1. Risk: Provider API differences make stream detection brittle.
   - Mitigation: adapter-level capability flag and per-provider tests.
2. Risk: Memory sampling overhead perturbs timing.
   - Mitigation: lightweight polling cadence with bounded interval.
3. Risk: AST validation crashes on malformed code.
   - Mitigation: catch parse exceptions and score failed checks deterministically.
4. Risk: Downstream consumer breakage.
   - Mitigation: maintain backward-safe reader behavior and compatibility tests.

## Ready-to-Start Task List
1. Create telemetry types and formatter utility.
2. Instrument generation wrapper for latency and peak RSS capture.
3. Add `ConstraintValidator` with regex and AST rule support.
4. Wire telemetry into report writer.
5. Add unit/integration tests and run full gates.
