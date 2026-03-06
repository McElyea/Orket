# Runtime Stability Focus Requirements

Last updated: 2026-03-06  
Status: Active (requirements draft)  
Owner: Orket Core

## Purpose

Define requirements for the current runtime-stability focus items before implementation planning.

## Scope

In scope:
1. Focus items 1-6 and directly related guardrails.
2. Behavioral contracts, interfaces, observability, failure semantics, and proof gates.
3. Alignment with local-model reliability and drift detection goals.

Out of scope:
1. Sprint sequencing and execution plan details.
2. Full implementation of all compatibility tools.
3. Roadmap reprioritization outside the active techdebt lane.

## Focus Item 1: Split System Into Core vs Workloads

### Goal

Stabilize runtime behavior by isolating experimentation inside workloads while core contracts remain deterministic.

### Related Items

1. Tool sandbox profiles.
2. Experiment flags.
3. Workload templates.
4. Capability profiles.
5. Artifact schema registry.
6. Tool schema compatibility matrix.

### Requirements

Behavior:
1. `core/` owns canonical contracts only:
   1. response protocol
   2. runtime execution engine
   3. run ledger
   4. artifact schema registry
   5. tool contract definitions
2. `workloads/` orchestrate behavior but cannot bypass runtime contracts.
3. Workloads may invoke only tools declared in their capability profile.
4. Core runtime must remain deterministic regardless of workload behavior.
5. Tool schema compatibility is validated at load time and run time.

Interfaces:
1. Core exposes stable entrypoints:
   1. `execute_run(workload, input)`
   2. `execute_tool(tool_name, args)`
   3. `record_artifact(type, payload)`
   4. `record_ledger_event(event)`
2. Workloads expose lifecycle hooks:
   1. `plan()`
   2. `execute()`
   3. `evaluate()`
3. Workloads cannot import core-internal modules directly.

Observability:
1. Each run records:
   1. `run.json`
   2. `capability_profile.json`
   3. `workload_identity.json`
   4. `core_version.json`
2. Boundary violations emit `runtime_violation.json`.

Failure semantics:
1. Workload exceptions cannot crash the runtime.
2. Invalid tool access fails closed with stable error codes.
3. Contract violations are rejected by core.
4. Example:
   1. `{"error":"capability_violation","tool":"shell.exec"}`

Proof:
1. Static checks enforce dependency direction.
2. Runtime guard tests exercise illegal tool access.
3. CI fails if workloads import core internals.
4. Sandbox tests prove workload isolation.

## Focus Item 2: Golden Run Harness

### Goal

Detect behavioral drift across prompts, tool envelopes, runtime behavior, and artifacts.

### Related Items

1. Deterministic replay mode.
2. Prompt diff.
3. Run determinism tests.
4. Contract hash pinning.
5. Drift classifier.

### Requirements

Behavior:
1. Golden runs define reference behavior.
2. Each fixture contains:
   1. `input.json`
   2. `expected_tool_calls.json`
   3. `expected_artifacts.json`
   4. `expected_status.json`
3. Golden runs execute in:
   1. `live_mode`
   2. `replay_mode` (no LLM invocation)

Interfaces:
1. `orket run golden/<test>`
2. `orket replay golden/<test>`
3. Comparator modes:
   1. `strict`
   2. `normalized`
   3. `artifact_hash`

Observability:
1. Capture:
   1. `contract_hash`
   2. `prompt_hash`
   3. `tool_schema_hash`
   4. `model_id`
   5. `orket_version`
2. Drift outputs `drift_report.json`.

Failure semantics:
1. Unexpected drift fails CI.
2. Accepted drift must be classified.
3. Non-deterministic artifacts are rejected unless explicitly allowed.

Proof:
1. Replay of a golden fixture is artifact-identical.
2. Drift classifier identifies drift layer correctly.

## Focus Item 3: Prompt Surface Budgets

### Goal

Prevent prompt bloat and preserve reliability on local models.

### Related Items

1. Stage-level budgets.
2. Prompt minimizer.
3. Prompt-pattern linter.
4. Prompt diff.

### Requirements

Behavior:
1. Budget enforcement per stage:
   1. planner
   2. executor
   3. reviewer
2. Per-stage limits include:
   1. `max_tokens`
   2. `protocol_tokens`
   3. `tool_schema_tokens`
   4. `task_tokens`
3. Exceeding hard limits fails closed.

Interfaces:
1. Budget config source: `prompt_budget.yaml`.
2. Runtime check API: `check_prompt_budget(prompt)`.
3. Optional reduction API: `minimize_prompt(prompt)`.

Observability:
1. Record `prompt_budget_usage.json` each run.
2. Emit prompt diffs to `prompt_diff.txt` on structural changes.

Failure semantics:
1. Exceed budget => `{"error":"prompt_budget_exceeded"}`.
2. Run exits with failure status.

Proof:
1. Budget enforcement test suite.
2. Deterministic token accounting.
3. Prompt diff coverage for structural changes.

## Focus Item 4: Tool Reliability Scoreboard

### Goal

Measure real reliability by tool/model/workload and make prioritization data-driven.

### Related Items

1. Telemetry dashboard.
2. Model performance profiles.
3. Tool heatmap.
4. Retry reason taxonomy.
5. Workload SLOs.

### Requirements

Behavior:
1. Record per-invocation metrics:
   1. attempts
   2. success/failure
   3. latency
   4. retry_count
   5. failure_class
2. Segment by:
   1. tool
   2. model
   3. workload
   4. version

Interfaces:
1. Ingestion API: `record_tool_metric(event)`.
2. Query API: `tool_metrics(tool_name)`.

Observability:
1. Emit `tool_scoreboard.json`.
2. Dashboard views include:
   1. tool heatmap
   2. model success chart
   3. retry histogram

Failure semantics:
1. Classify failures with stable codes:
   1. `tool_timeout`
   2. `invalid_args`
   3. `runtime_error`
   4. `model_error`

Proof:
1. Scoreboard is reconstructable from ledger events only.

## Focus Item 5: Run Compression (`run_summary.json`)

### Goal

Produce a concise run artifact that preserves auditability and replay traceability.

### Related Items

1. Run graph visualization.
2. Artifact schema registry.
3. Provenance chain.
4. Retention tiers.

### Requirements

Behavior:
1. Every run generates `run_summary.json`.
2. Summary contains:
   1. `run_id`
   2. `status`
   3. `duration_ms`
   4. `tools_used`
   5. `artifact_ids`
   6. `failure_reason`
3. Summary is derivable from ledger state.

Interfaces:
1. `generate_run_summary(run_id)`.

Observability:
1. Graph generation can consume summary directly.

Failure semantics:
1. Summary generation failure does not invalidate original run result.
2. Summary generation failure is still logged as a separate error event.

Proof:
1. Reconstructed summary matches emitted summary content.

## Focus Item 6: Core Tool Baseline

### Goal

Define a deterministic baseline toolset that is small enough to stabilize and broad enough to support OpenClaw-class workflows through compatibility rings.

### Related Items

1. Tool intent hints.
2. Tool call validator.
3. Structured errors.
4. Timeout governance.
5. Retry policies.
6. Capability profiles.
7. Tool rings and compatibility contract.

Reference:
1. `docs/projects/core/core_tool_rings_compatibility_requirements.md`

### Requirements

Behavior:
1. Core baseline tool count is a minimum floor, not a fixed cap.
2. Each tool must declare:
   1. `input_schema`
   2. `output_schema`
   3. `error_schema`
   4. `determinism_class` (`pure`, `workspace`, `external`)
   5. `side_effect_class`
   6. timeout policy
   7. retry policy
3. All tool errors are machine-readable and stable.
4. Compatibility expansion cannot weaken core determinism rules.

Interfaces:
1. Tool definition includes:
   1. `tool_name`
   2. `schema_version`
   3. `timeout`
   4. `retry_policy`
   5. `capability_profile`

Observability:
1. Emit per invocation:
   1. `tool_call.json`
   2. `tool_result.json`
   3. `tool_metrics.json`

Failure semantics:
1. Invalid args and schema mismatch fail closed.
2. Structured errors remain stable across versions.

Proof:
1. Every baseline tool has:
   1. conformance tests
   2. schema validation tests
   3. determinism tests
2. Compatibility tools additionally require parity tests against mapped behavior.

## Decision Constraint: Baseline Count vs OpenClaw Match

1. Do not hard-cap baseline capability at exactly 10 tools.
2. Treat 10 as a stabilization floor for deterministic core coverage.
3. Expand breadth via compatibility ring first, then promote to core only after reliability and parity gates pass.
4. Promotion gates are defined in `core_tool_rings_compatibility_requirements.md`.
