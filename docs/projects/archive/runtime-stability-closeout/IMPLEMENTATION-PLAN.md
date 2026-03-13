# Runtime Stability Structural Closeout Plan

Last updated: 2026-03-13
Status: Archived
Owner: Orket Core

Archive note: Historical planning record preserved after the runtime-stability structural closeout lane completed on 2026-03-13. See `docs/projects/archive/runtime-stability-closeout/CLOSEOUT.md` for the archive summary.

## Purpose

Close out the runtime-stability ideas that were removed from `docs/projects/future/Idea-Parking-Lot-2026-03-06.md` using structural proof instead of parking-lot phrasing.

This lane answers three questions for each removed item:
1. what shipped code and proof already exist,
2. what work still remains before the item can be honestly called complete,
3. what test or proof will be required to make that closeout truthful.

## Decision Lock Rule

Every direct slice implementation plan under this lane must open with exactly two lines under a `Decision Lock` section:
1. `Chosen closeout target: ...`
2. `Explicitly excluded target(s): ...`

Do not reopen excluded branches inside the same slice plan without an explicit roadmap-level scope change.

## Structural Proof Inputs

Primary sources for this lane:
1. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
2. `docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md`
3. `docs/specs/CONTROLLER_WORKLOAD_V1.md`
4. `docs/projects/archive/core/runtime_requirements_slice_workboard.md`
5. `docs/projects/archive/controller-workload/CW03082026-Phase2D/07-V1-PLANNING-HANDOFF.md`
6. `tests/reports/replay_integrity_test_report.json`
7. `tests/reports/prompt_budget_tokenizer_truth_report.json`
8. `tests/reports/scoreboard_promotion_gate_report.json`
9. `tests/reports/run_graph_reconstruction_report.json`
10. `tests/reports/compat_mapping_governance_report.json`
11. `tests/reports/compat_pilot_parity_report.json`

## Classification Rules

This lane uses the following closeout states:
1. `structurally complete`: shipped code and existing structural proof already match the scoped claim.
2. `promoted but not closed`: the idea is no longer just parked, but the shipped code or proof does not yet satisfy the stronger requirement text.
3. `decision locked`: the closeout branch is explicitly chosen and a direct implementation plan exists, but the narrowing or proof work is not complete yet.

## Closeout Matrix

| Slice ID | Removed item group | Current closeout state | Why |
|---|---|---|---|
| SPC-01 | core vs workloads boundary | structurally complete | active requirements were narrowed to the shipped v0 boundary contract and the boundary proof set is green |
| SPC-02 | golden run harness + deterministic replay + run determinism tests | structurally complete | protocol replay is the canonical operator surface and the CLI, script, and replay proof set is green |
| SPC-03 | prompt surface budgets + prompt diff tooling | structurally complete | implementation and targeted proof already match the scoped claim |
| SPC-04 | tool reliability scoreboard | structurally complete | ledger-only scoreboard generation and promotion proof are already landed |
| SPC-05 | run compression + run graph visualization + artifact schema registry | structurally complete | canonical `run_summary.json` emission, schema validation, reconstruction, and parity proof are landed |
| SPC-06 | core tool baseline + capability profiles per workload | structurally complete | active requirements now match the shipped minimal registry and invocation-manifest contract, and the proof set is green |

## Execution Routing

Route the removed items by coverage level:
1. Archived direct closeout plans:
   1. SPC-01
      Authority: `docs/projects/archive/runtime-stability-closeout/SPC-01-BOUNDARY-CLOSEOUT-IMPLEMENTATION-PLAN.md`
   2. SPC-02
      Authority: `docs/projects/archive/runtime-stability-closeout/SPC-02-GOLDEN-HARNESS-CLOSEOUT-IMPLEMENTATION-PLAN.md`
   3. SPC-05
      Authority: `docs/projects/archive/runtime-stability-closeout/SPC-05-RUN-SUMMARY-CLOSEOUT-IMPLEMENTATION-PLAN.md`
   4. SPC-06
      Authority: `docs/projects/archive/runtime-stability-closeout/SPC-06-CORE-TOOL-BASELINE-CLOSEOUT-IMPLEMENTATION-PLAN.md`
2. Certified structural closeout at archive time:
   1. SPC-03
   2. SPC-04

## Slice Evaluations

### SPC-01: Core vs Workloads Boundary

Current structural proof:
1. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md` Focus Item 1 defines the target split and required boundary artifacts.
2. `docs/specs/CONTROLLER_WORKLOAD_V1.md` locks current authoritative controller/workload behavior, including sequential child execution, fail-closed dispatch, and deterministic summary expectations.
3. `docs/projects/archive/controller-workload/CW03082026-Phase2D/07-V1-PLANNING-HANDOFF.md` explicitly says the current baseline remains v0 and that broader v1 work is still planning input only.
4. Runtime enforcement already exists for `capability_manifest.json`, `run_determinism_class`, ring policy, and capability-profile rejection in `orket/runtime/run_start_artifacts.py`, `orket/application/workflows/orchestrator_ops.py`, and `orket/application/workflows/turn_tool_dispatcher_support.py`.

Structural gaps preventing honest closeout:
1. The Focus Item 1 artifact set includes `capability_profile.json`, `workload_identity.json`, and `runtime_violation.json`, but those artifacts are not currently evidenced by the shipped code or proof reports used here.
2. The roadmap still stages `controller-workload v1 kickoff`, so boundary evolution beyond the locked v0 contract is explicitly unfinished.

Remaining work:
1. Narrow the active requirement text to the current v0 boundary behavior.
2. Remove active claims for `capability_profile.json`, `workload_identity.json`, and `runtime_violation.json`.
3. Tighten proof for the shipped v0 artifact set and fail-closed policy rejection.

Required completion proof:
1. Static boundary/import checks remain green.
2. Contract and integration tests prove the narrowed v0 boundary claim.
3. Controller replay/parity suites remain green after the closeout change.

Routing decision:
1. Completed via `docs/projects/archive/runtime-stability-closeout/SPC-01-BOUNDARY-CLOSEOUT-IMPLEMENTATION-PLAN.md`.

### SPC-02: Golden Run Harness + Deterministic Replay + Run Determinism Tests

Current structural proof:
1. `tests/reports/replay_integrity_test_report.json` marks `CORE-IMP-02` done with replay, drift-classifier, compatibility-rejection, and determinism-campaign coverage.
2. `orket/interfaces/cli.py` ships `orket protocol replay <run_id>`, `compare`, `campaign`, and parity commands over recorded run data.

Structural gaps preventing honest closeout:
1. Focus Item 2 promises `orket run golden/<test>` and `orket replay golden/<test>`, but the current CLI surface is run-id-based protocol replay rather than fixture-based golden replay.
2. The required golden fixture shape (`input.json`, `expected_tool_calls.json`, `expected_artifacts.json`, `expected_status.json`) is specified, but a canonical fixture runner/storage path is not yet evidenced by the current runtime surface.

Remaining work:
1. Narrow the active requirement text to the shipped protocol replay surface.
2. Remove active claims for `orket run golden/<test>` and `orket replay golden/<test>`.
3. Tighten CLI and script-layer proof for the chosen protocol replay operator surface.

Required completion proof:
1. CLI and script tests for the chosen canonical interface.
2. End-to-end protocol replay proof at the user-facing harness layer.
3. Drift-classification tests at that same operator layer, not only at raw run-id replay level.

Routing decision:
1. Completed via `docs/projects/archive/runtime-stability-closeout/SPC-02-GOLDEN-HARNESS-CLOSEOUT-IMPLEMENTATION-PLAN.md`.

### SPC-03: Prompt Surface Budgets + Prompt Diff Tooling

Current structural proof:
1. `tests/reports/prompt_budget_tokenizer_truth_report.json` marks `CORE-IMP-05` done with `140` passing tests.
2. Shipped runtime paths already load `core/policies/prompt_budget.yaml`, enforce fail-closed prompt budgets, and emit `prompt_budget_usage.json`, `prompt_structure.json`, and `prompt_diff.txt`.

Closeout position:
1. This slice is structurally complete for the scoped claim that was removed from the parking lot.

Remaining work:
1. None required for honest structural closeout.
2. Optional future confidence work: live-provider acceptance against real backend tokenizer counts.

Required completion proof:
1. Keep the existing contract and integration suite green.
2. If live-proof uplift is desired later, run a real provider-backed prompt-budget acceptance slice and record observed path/result explicitly.

Routing decision:
1. No new lane required unless contradictory evidence appears.

### SPC-04: Tool Reliability Scoreboard

Current structural proof:
1. `tests/reports/scoreboard_promotion_gate_report.json` marks `CORE-IMP-06` done with ledger-only reproducibility and promotion-gate tests.
2. `orket/runtime/tool_scoreboard.py` and `scripts/governance/generate_tool_scoreboard.py` already compute and publish rerunnable `tool_scoreboard.json` artifacts from ledger evidence only.

Closeout position:
1. This slice is structurally complete for the removed scoreboard claim.

Remaining work:
1. None for scoreboard closeout itself.
2. Follow-on observability work such as dashboard, heatmap, and workload/model profiling remains outside this slice.

Required completion proof:
1. Keep the existing runtime and platform scoreboard tests green.
2. Optional confidence uplift: regenerate the scoreboard from a recorded live ledger sample and compare it to the checked-in structural expectations.

Routing decision:
1. No new lane required unless contradictory evidence appears.

### SPC-05: Run Compression + Run Graph Visualization + Artifact Schema Registry

Current structural proof:
1. `tests/reports/run_graph_reconstruction_report.json` marks `CORE-IMP-08` done and proves deterministic `run_graph.json` reconstruction and emission.
2. The artifact schema registry is shipped at `core/artifacts/schema_registry.yaml` and validated by `orket/runtime/contract_bootstrap.py`.
3. `run_summary.json` is present in the schema registry, retention tiers, and requirements text.
4. `orket/runtime/execution_pipeline.py` includes `_build_run_summary(...)`, and subsystem-specific summary outputs exist for some coordinator flows.

Structural gaps preventing honest closeout:
1. The requirement interface `generate_run_summary(run_id)` is specified but not currently implemented as a generic runtime surface.
2. A canonical runtime path that emits `run_summary.json` for every run is not clearly evidenced by the shipped protocol-finalize path or current proof reports.
3. Existing summary builders appear to be pipeline- or subsystem-local rather than the canonical derivation contract promised by the spec.

Remaining work:
1. Implement canonical runtime `run_summary.json` generation from ledger/artifact state.
2. Add a declared summary schema and deterministic reconstruction rules.
3. Align emitted summary content, ledger `summary_json`, and run-graph consumption around that canonical artifact.

Required completion proof:
1. Contract tests for summary schema and deterministic reconstruction.
2. Integration tests proving summary emission on success, failed, and blocked run finalization paths.
3. Replay-parity tests that compare emitted or reconstructed summaries across equivalent live and replay runs.

Routing decision:
1. Completed via `docs/projects/archive/runtime-stability-closeout/SPC-05-RUN-SUMMARY-CLOSEOUT-IMPLEMENTATION-PLAN.md`.

### SPC-06: Core Tool Baseline + Capability Profiles Per Workload

Current structural proof:
1. `tests/reports/compat_mapping_governance_report.json` and `tests/reports/compat_pilot_parity_report.json` mark compatibility governance and pilot parity slices done.
2. `core/tools/tool_registry.yaml` already records a minimal core-tool baseline and `capability_profile` per tool.
3. Runtime preflight enforces `allowed_capability_profiles`, ring policy, and determinism policy before execution.

Structural gaps preventing honest closeout:
1. The baseline-tool spec promises `input_schema`, `output_schema`, `error_schema`, `side_effect_class`, timeout policy, and retry policy per tool, but the current tool registry and bootstrap parser validate only:
   1. `tool_name`
   2. `ring`
   3. `tool_contract_version`
   4. `determinism_class`
   5. `capability_profile`
2. The current core baseline contains only five `workspace` tools, so the completion target for "broad enough to support OpenClaw-class workflows" is still ambiguous unless the claim is narrowed.
3. Capability profiles are enforced, but the fuller baseline-tool metadata contract is not yet canonical at the registry layer.

Remaining work:
1. Narrow the active requirement text to the current minimal baseline and current registry fields.
2. Remove active claims for richer per-tool metadata and expanded baseline breadth from the closeout scope.
3. Tighten proof for the current bootstrap, dispatcher, and artifact surfaces that actually enforce the chosen minimal contract.

Required completion proof:
1. Contract tests for the current tool-registry schema and fail-closed validation.
2. Dispatcher integration tests proving the current capability-profile and ring-policy metadata is present and enforced where claimed.
3. Artifact-surface checks only where the narrowed minimal contract claims those fields.

Routing decision:
1. Completed via `docs/projects/archive/runtime-stability-closeout/SPC-06-CORE-TOOL-BASELINE-CLOSEOUT-IMPLEMENTATION-PLAN.md`.

## Recommended Execution Order

1. Historical execution completed on 2026-03-13 through the SPC-01, SPC-02, SPC-05, and SPC-06 closeout plans.
2. SPC-03 and SPC-04 remained certified structural closeouts throughout the lane.

## Exit Criteria For This Lane

Archive outcome: satisfied on 2026-03-13 once every removed item reached one of these states:
1. structurally complete with existing proof still green, or
2. closed by bounded implementation plus proof, or
3. explicitly narrowed by truthful source-of-truth updates so the smaller shipped claim is the canonical claim.

The lane must not close with silent spec drift between:
1. `docs/specs/`
2. runtime code
3. proof reports
4. CLI/runtime entrypoints
