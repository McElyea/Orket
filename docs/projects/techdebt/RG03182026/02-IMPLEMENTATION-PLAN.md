# RG03182026 Phase 1 Runtime Gap Implementation Plan

Last updated: 2026-03-18
Status: Active
Owner: Orket Core
Lane type: Active techdebt cycle

Requirements authority:
1. [docs/projects/techdebt/RG03182026/01-REQUIREMENTS.md](docs/projects/techdebt/RG03182026/01-REQUIREMENTS.md)

## Goal

Resolve the runtime gaps surfaced by Phase 1 without widening scope into a general orchestrator rewrite.

This plan makes three explicit choices:

1. freeze the current cards runtime as `builder_guard_app_v1` instead of pretending it is a general card path
2. work into `builder_guard_artifact_v1` by reusing `coder` with a profile-driven artifact contract rather than duplicating the builder role
3. fix ODR in two steps:
   1. harden prompt, parser, semantic validity, auditor enforcement, leak, and stop-reason behavior on the standalone path
   2. integrate ODR as an explicit pre-build profile or stage rather than a hidden per-turn rewrite

## Recommended Direction

### Cards Choice

1. Current choice to preserve truthfully:
   1. `builder_guard_app_v1`
   2. app-centric builder/guard flow
   3. `agent_output/main.py` as the default runnable artifact
2. Recommended next choice:
   1. `builder_guard_artifact_v1`
   2. explicit artifact contract on the issue or epic
   3. no hidden path coercion to `agent_output/main.py`
3. Deferred future choice:
   1. a broader staged role pipeline such as `full_pipeline_v1`
   2. not part of this lane unless the bounded artifact-profile approach proves insufficient

### Coder Choice

1. Recommended:
   1. keep `coder` as the canonical builder role
   2. move path requirements out of role-name hard-coding and into profile-aware artifact-contract resolution
2. Not recommended:
   1. adding a second canonical builder role just to get a different output path
3. Interim fallback while the artifact profile is being built:
   1. fail closed if the app profile is selected for non-app work

### ODR Choice

1. Recommended:
   1. fix ODR first as a standalone governed semantic specification loop
   2. integrate it second as an explicit pre-build refinement path
2. Not recommended:
   1. wiring current unstable ODR directly into every cards turn
   2. relaxing parsers silently until the five-run baseline looks green

## Workstream 1: Freeze and Expose the Current Cards Profile

Objective:
1. Turn the current implicit app-centric path into an explicit runtime choice.

Primary surfaces:
1. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py)
2. [orket/application/services/runtime_policy.py](orket/application/services/runtime_policy.py)
3. [orket/runtime/execution_pipeline.py](orket/runtime/execution_pipeline.py)

Actions:
1. Add an explicit execution-profile concept and emit it from runtime selection.
2. Map the current live small-project behavior to `builder_guard_app_v1`.
3. Emit profile, builder-seat choice, reviewer-seat choice, and any seat coercion in runtime events and run summary.
4. Add a canonical cards `stop_reason` surface to run summary generation.

Acceptance:
1. A reviewer can identify the profile and routing choices from artifacts alone.
2. The current cards path is no longer described as a general artifact workflow.

Proof target:
1. structural

## Workstream 2: Introduce an Artifact Contract Source of Truth

Objective:
1. Make non-app artifact work first-class without creating a duplicate builder role.

Primary surfaces:
1. [orket/application/workflows/turn_path_resolver.py](orket/application/workflows/turn_path_resolver.py)
2. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py)
3. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py)
4. any minimal schema surface required for issue or epic artifact-contract fields

Actions:
1. Define a minimal artifact-contract shape for cards issues or epics.
2. Route required read and write paths through one shared resolver instead of repeating role-name defaults.
3. Add explicit preflight that rejects invalid profile/task combinations before the first model turn.
4. Make the requested artifact contract visible in runtime events and run summary.

Acceptance:
1. There is one source of truth for required artifact paths.
2. The runtime can tell app work from artifact work before dispatch.

Proof target:
1. structural

## Workstream 3: Uncouple Builder, Reviewer, Guard, and Planner Assumptions from `main.py`

Objective:
1. Remove `agent_output/main.py` as a hidden global requirement outside the app profile.

Primary surfaces:
1. [orket/application/services/prompt_compiler.py](orket/application/services/prompt_compiler.py)
2. [orket/application/services/canonical_role_templates.py](orket/application/services/canonical_role_templates.py)
3. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py)
4. [orket/application/workflows/turn_contract_validator.py](orket/application/workflows/turn_contract_validator.py)
5. [orket/application/workflows/turn_corrective_prompt.py](orket/application/workflows/turn_corrective_prompt.py)
6. [orket/application/services/deployment_planner.py](orket/application/services/deployment_planner.py)
7. [orket/runtime/live_acceptance_assets.py](orket/runtime/live_acceptance_assets.py)

Actions:
1. Make prompt instructions profile-aware and artifact-contract-aware.
2. Derive reviewer and guard read paths from the same artifact contract.
3. Keep deployment planner app-specific and gated by profile or artifact intent.
4. Preserve `agent_output/main.py` only where the declared contract actually wants a runnable Python entrypoint.
5. Update live assets and probes so both app and artifact profiles can be exercised.

Acceptance:
1. P-01 artifact-profile runs can target a requested artifact path truthfully.
2. P-03 artifact-profile runs do not fail due to a forced `agent_output/main.py` contract.

Proof target:
1. contract test
2. integration test
3. live

## Workstream 4: Harden ODR Prompt, Parser, Validity, Auditor, and Leak Surfaces

Objective:
1. Reduce live ODR fragility and close semantic evasion paths without lying about the model outputs.

Primary surfaces:
1. [orket/kernel/v1/odr/core.py](orket/kernel/v1/odr/core.py)
2. [orket/kernel/v1/odr/parsers.py](orket/kernel/v1/odr/parsers.py)
3. [orket/kernel/v1/odr/leak_policy.py](orket/kernel/v1/odr/leak_policy.py)
4. [scripts/probes/p02_odr_isolation.py](scripts/probes/p02_odr_isolation.py)
5. [scripts/odr/run_odr_7b_baseline.py](scripts/odr/run_odr_7b_baseline.py)
6. [scripts/odr/run_odr_live_role_matrix.py](scripts/odr/run_odr_live_role_matrix.py)

Actions:
1. Freeze one canonical live ODR prompt contract with deterministic role templates and examples.
2. Add a governed semantic validity validator separate from format parsing.
3. Record per round:
   1. validity verdict
   2. pending decision count
   3. contradiction count
   4. constraint-demotion violations
   5. repair classes, if any
4. Formalize auditor patch classes:
   1. `ADD`
   2. `REMOVE`
   3. `REWRITE`
   4. `DECISION_REQUIRED`
5. Reject rounds that:
   1. move required constraints into `ASSUMPTIONS` or `OPEN_QUESTIONS`
   2. preserve unresolved mandatory alternatives
   3. remove required constraints without stronger replacement
6. Add governed stop reasons for:
   1. `INVALID_CONVERGENCE`
   2. `UNRESOLVED_DECISIONS`
7. Keep weak-token leak observations as warnings unless stronger structural evidence exists.
8. Tune only one ODR surface at a time:
   1. prompt shape
   2. parser handling
   3. validity rules
   4. auditor enforcement
   5. leak policy
   6. convergence thresholds
9. Use the five-run live baseline as the canonical red/green measure.

Acceptance:
1. Five-run live baseline produces at most one `FORMAT_VIOLATION`.
2. No legitimate requirements run stops on weak-token-only `CODE_LEAK`.
3. A required constraint cannot disappear into `ASSUMPTIONS` or `OPEN_QUESTIONS` without a validator failure.
4. Stable invalid outputs stop as `INVALID_CONVERGENCE`, not success.
5. Runs with unresolved required decisions stop as `UNRESOLVED_DECISIONS` unless resolved by governed fallback.
6. Trace artifacts make it obvious whether a win came from prompt hardening, parser repair, validity enforcement, auditor enforcement, leak calibration, or convergence tuning.

Proof target:
1. contract test
2. integration test
3. live

## Workstream 5: Integrate ODR as an Explicit Cards Stage

Objective:
1. Add ODR to cards truthfully and observably instead of implying integration that does not exist.

Primary surfaces:
1. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py)
2. [orket/runtime/execution_pipeline.py](orket/runtime/execution_pipeline.py)
3. [scripts/probes/p04_odr_cards_integration.py](scripts/probes/p04_odr_cards_integration.py)

Actions:
1. Add an explicit ODR-backed cards path such as `odr_prebuild_builder_guard_v1`.
2. Run ODR before the builder turn and persist:
   1. `history_rounds`
   2. ODR `stop_reason`
   3. accepted refined requirement or explicit ODR failure result
   4. `odr_valid`
   5. `odr_pending_decisions`
3. Emit `odr_active=true` when this path is selected and `odr_active=false` otherwise.
4. Keep the normal non-ODR cards path intact while the ODR-backed path proves itself.

Acceptance:
1. P-04 can distinguish non-ODR cards runs from ODR-enabled cards runs.
2. ODR-enabled cards runs emit direct ODR artifacts and summary fields, including `odr_valid` and `odr_pending_decisions`.

Proof target:
1. structural
2. live

## Workstream 6: Re-Prove the Phase 1 Surfaces and Close the Lane

Objective:
1. Use the original Phase 1 probes as the canonical closure gate.

Actions:
1. Re-run provider preflight on the selected local model.
2. Re-run P-01 on `builder_guard_app_v1` and `builder_guard_artifact_v1`.
3. Re-run P-03 on `builder_guard_artifact_v1`.
4. Re-run the five-run P-02 live baseline.
5. Re-run P-04 against:
   1. a non-ODR cards run
   2. an ODR-enabled cards run
6. Update active docs if any claim remains narrower than the preferred closure path.

Acceptance:
1. The Phase 1 probe set now describes the runtime as it actually is after remediation, not before it.
2. Closure evidence is live for the cards and ODR paths wherever the lane made a live behavior claim.

Proof target:
1. live
2. structural

## Verification Plan

Structural gates:
1. targeted tests added or updated for the touched runtime surfaces
2. source review confirming one artifact-contract source of truth
3. decision-required propagation from seed decisions into `REQUIREMENT`-level `DECISION_REQUIRED`
4. rejection of constraint demotion into `ASSUMPTIONS` or `OPEN_QUESTIONS`
5. rejection of unresolved `either/or` behavior alternatives
6. `INVALID_CONVERGENCE` classification for stable invalid loops
7. `UNRESOLVED_DECISIONS` classification at max rounds
8. auditor monotonicity: required constraints cannot be removed without stronger replacement
9. `python scripts/governance/check_docs_project_hygiene.py`

Canonical live gates:
1. `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --smoke-stream`
2. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p01_single_issue.py --workspace <temp_app_profile> --model qwen2.5-coder:7b --json`
3. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p01_single_issue.py --workspace <temp_artifact_profile> --model qwen2.5-coder:7b --json`
4. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p03_epic_trace.py --workspace <temp_p03_profile> --model qwen2.5-coder:7b --json`
5. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p02_odr_isolation.py --model qwen2.5-coder:7b --runs 5 --json`
6. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p04_odr_cards_integration.py --workspace <temp_cards_workspace> --session-id <session_id> --json`

## Stop Conditions

1. Stop and split the lane if artifact-contract support requires a repo-wide card-schema redesign rather than a bounded runtime contract change.
2. Stop and narrow the claim truthfully if ODR cannot meet the live-baseline target without unsafe silent parsing or misleading contract relaxation.
3. Stop if the chosen path requires duplicating the canonical builder role instead of reusing `coder` with clearer contract boundaries.

## Completion Gate

1. The requirements conclusive gate in [docs/projects/techdebt/RG03182026/01-REQUIREMENTS.md](docs/projects/techdebt/RG03182026/01-REQUIREMENTS.md) is green.
2. The roadmap can continue to point at this plan until lane closeout.
3. When the lane closes, archive the cycle under `docs/projects/archive/techdebt/RG03182026/`.
