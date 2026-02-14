# Orket Roadmap (Active Only)

Last updated: 2026-02-14.

## North Star
Ship one canonical, reliable pipeline that passes this exact flow:
1. `requirements_analyst`
2. `architect`
3. `coder`
4. `code_reviewer`
5. `integrity_guard`

If this flow is not mechanically proven with canonical assets, we are not done.

## Core Idea
1. Roles are stable contracts.
2. Models are unique specialists, not interchangeable workers.
3. Model assignment is capability-aware by role and stage.
4. Governance and stage gates absorb model variance and enforce deterministic outcomes.

## Completed This Session (Removed From Active Work)
1. Durable state migration landed and defaults now resolve under `.orket/durable/`.
2. Legacy runtime DB and observability DB paths were migrated to durable locations.
3. Gitea artifact cache/staging moved from `.orket/gitea_artifacts` to `.orket/durable/gitea_artifacts`.
4. Documentation map file was removed; docs navigation is now direct from `README.md`.
5. Architecture docs were consolidated to `docs/ARCHITECTURE.md` as canonical authority.
6. Canonical model asset integrity gate added and passing (`tests/platform/test_model_asset_integrity.py`).
7. Missing core role/team assets repaired for canonical loader/runtime viability.
8. Acceptance fixture aligned to architect decision contract JSON schema.
9. Acceptance loop now suppresses sandbox deploy attempts by default (`ORKET_DISABLE_SANDBOX=1` in loop runner).
10. `P-1A` scaffolder stage landed and is enforced pre-loop with deterministic structure checks.
11. `P-1B` dependency manager stage landed with opt-in dependency file ownership gate in `ToolGate`.
12. `P-1C` runtime verifier stage landed to block review dispatch when generated code fails compile verification.
13. `P-1D` deployment planner stage landed with deterministic deployment baseline assets.
14. Runtime verifier now emits machine-readable report artifact at `agent_output/verification/runtime_verification.json`.
15. Runtime verifier now supports policy-driven command matrix execution and optional deployment-file validation hooks.
16. Live acceptance loop now records and prints explicit `chain_complete` signal per run.
17. Live loop evidence now captures `session_status=done` but `chain_complete=false` mismatches for targeted follow-up in `P0`.

## Current Status Snapshot
1. `P-1 Pipeline Stabilizers`: Active, foundational slices (`P-1A` to `P-1D`) landed.
2. `P0 Data-Driven Behavior Recovery Loop`: Active, now downstream of `P-1`.
3. `P1 Canonical Assets Runnable`: Active, major integrity slice completed.
4. `P2 Acceptance Gate Uses Canonical Assets`: In progress.
5. `P3 Boundary Enforcement`: Guardrail mode (maintain only).
6. `P4 Documentation Reset`: Completed for current baseline.

## Operating Rules
1. Simple over clever.
2. No broad refactors while recovery work is active.
3. Fix only what blocks the acceptance contract.
4. Every change must be tied to a failing or missing test.
5. Implement stabilizers as stage/seat contracts on existing `ISSUE` flow first (no new `CardType` until proven necessary).

## P-1: Pipeline Stabilizers (Highest Priority)
Objective: harden Orket from prototype behavior into deterministic pipeline behavior by adding four stabilizer stages around the existing chain.

Why this is above P0:
1. P0 improves behavior quality; P-1 reduces structural churn that keeps reintroducing failures.
2. Existing seams already support this (`DecisionNode` contracts, `ToolGate`, `TurnExecutor` contracts, state machine enforcement).
3. This is additive guardrail work, not an orchestrator rewrite.

Implementation policy:
1. Keep the canonical role chain (`requirements_analyst -> architect -> coder -> code_reviewer -> integrity_guard`) intact.
2. Add stabilizers as pre/post stages and ownership contracts, not architecture pivots.
3. Enforce deterministic outputs and file ownership through `ToolGate` and stage contracts.
4. Ship in small slices with tests for each gate.

### P-1A Scaffolder Stage
Goal: create deterministic project structure before design/coding work begins.

Work:
1. [x] Add scaffolding stage contract before analyst/architect execution for build initialization.
2. [x] Define schema-driven scaffold templates (required dirs/files/placeholders/readme/env/test skeleton).
3. [x] Add guard checks for required/missing/forbidden paths at scaffold completion.
4. [x] Ensure stable output: same input template must produce same scaffold tree.

Done when:
1. Scaffold output is deterministic across reruns.
2. Missing required scaffold files fail early before coding turns.
3. Acceptance artifacts include scaffold baseline for reviewer/guard reads.

Verification:
1. `python -m pytest tests/application/test_orchestrator_epic.py -q`
2. `python -m pytest tests/live/test_system_acceptance_pipeline.py -q`

### P-1B Dependency Manager Stage
Goal: centralize dependency and environment ownership away from coder turns.

Work:
1. [x] Add dependency-management stage after architecture decisions and before coder execution.
2. [x] Generate/maintain dependency manifests per stack (`pyproject.toml`, `requirements.txt`, `package.json`, etc.).
3. [~] Pin and validate dependency versions plus dev tooling dependencies.
4. [x] Enforce ownership in `ToolGate`: non-dependency stages cannot mutate dependency manifests.

Done when:
1. Dependency files are only writable by dependency-management stage.
2. Live runs show reduced dependency-related runtime failures/import misses.
3. Reviewer turns no longer perform dependency drift cleanup as routine work.

Verification:
1. `python -m pytest tests/application/test_orchestrator_epic.py -q`
2. `python scripts/run_live_acceptance_loop.py --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 2`

### P-1C Runtime Verifier Stage
Goal: fail fast on non-runnable output before review/guard turns.

Work:
1. [x] Add runtime-verification stage after coder output and before reviewer dispatch.
2. [~] Execute stack-appropriate checks (compile/build/test/type/lint) with deterministic command policy.
3. [x] Emit machine-readable pass/fail report artifacts and bind them into turn context.
4. [x] Gate reviewer dispatch on verifier pass; route failures back to coder with explicit diagnostics.

Done when:
1. Reviewer does not run when runtime verification fails.
2. Verifier reports are attached per run and visible in acceptance telemetry.
3. Broken-build churn shifts from review stage to coder fix loop.

Verification:
1. `python -m pytest tests/application/test_orchestrator_epic.py -q`
2. `python -m pytest tests/integration/test_system_acceptance_flow.py -q`

### P-1D Deployment Planner Stage
Goal: ensure every generated project has a deterministic runnable deployment plan.

Work:
1. [x] Add deployment-planning stage after architecture/dependency stages.
2. [x] Generate deployment assets (`Dockerfile`, compose, env schema, run scripts; optional k8s manifests by policy).
3. [x] Validate deployment assets against architecture and dependency contracts.
4. [~] Integrate deployment checks with runtime-verification policy.

Done when:
1. Deployment assets are present and structurally valid for generated projects.
2. Runtime verification can execute in a consistent local/container execution path.
3. Sandbox/deployment telemetry shows fewer configuration failures.

Verification:
1. `python -m pytest tests/adapters/test_sandbox_compose_generation.py -q`
2. `python -m pytest tests/live/test_system_acceptance_pipeline.py -q`

P-1 exit criteria:
1. All four stabilizer stages are contract-enforced and test-covered.
2. Role-chain completion variance drops across baseline model batches.
3. No stabilizer requires architecture rewrite or card-model pivot to operate.

## P0: Data-Driven Behavior Recovery Loop
Objective: use run evidence to systematically improve weak model behavior and raise canonical completion rate.

Why this remains critical:
1. Governance substrate is in place.
2. The primary blocker is repeated non-progress and guard over-blocking.
3. Telemetry is stable across raw artifacts, run ledger, and aggregate loop DB.

Inputs:
1. `.orket/durable/observability/live_acceptance_loop.db`:
   - `live_acceptance_batches`, `live_acceptance_runs`
2. Runtime run ledger (`run_ledger` rows in runtime DB).
3. Raw turn evidence:
   - `.pytest_live_loop/.../workspace/observability/.../checkpoint.json`
   - `workspace/default/orket.log` events

### P0-A Prompt Contract Reliability
Goal: reduce first-turn failures where required tool/status actions are missing.

Work:
1. Build per-role failure matrix from latest loop batches.
2. Harden prompts in this order: `requirements_analyst`, `architect`, `coder`.
3. Tighten corrective reprompt text with minimal valid response template.
4. Add targeted tests proving malformed single-tool response is corrected on first reprompt per role.

Done when:
1. `turn_non_progress` for `requirements_analyst` is below 5% over 20 baseline runs.
2. Deterministic `write_file`-only failures are absent for two consecutive baseline batches.

Verification:
1. `python scripts/run_live_acceptance_loop.py --models qwen2.5-coder:7b qwen2.5-coder:14b llama3.1:8b --iterations 3`

### P0-B Guard Decision Quality
Goal: stop premature guard blocks that propagate dependency failures.

Work:
1. Correlate `guard_rejected` events with prior-step completeness.
2. Keep strict rejection payload requirements:
   - non-empty rationale
   - at least one remediation action
3. Add tests for invalid rejection payload and valid rejection payload.

Done when:
1. Empty-rationale guard rejections are zero in baseline batches.
2. `dependency_block_propagated` caused by rationale-empty guard decisions is zero.

Verification:
1. `python -m pytest tests/application/test_orchestrator_epic.py -q`
2. `python scripts/run_live_acceptance_loop.py --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 3`

### P0-C Evidence Noise Control
Goal: keep acceptance telemetry focused on role-chain behavior, not sandbox environment failures.

Work:
1. [x] Add policy/env switch to disable sandbox deployment in acceptance-style runs.
2. [x] Apply sandbox-disable default in live acceptance loop driver.

Done when:
1. Acceptance loop logs no longer include irrelevant `sandbox_deploy_failed` noise by default.
2. Sandbox behavior remains opt-in for workflows that explicitly need it.

Verification:
1. `python -m pytest tests/application/test_orchestrator_epic.py -q`
2. `python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard -q`

P0 exit criteria:
1. Baseline models achieve >= 80% full-chain completion for two consecutive batches.
2. `turn_non_progress` is < 5% overall and < 10% for any single role in baseline set.
3. Empty-rationale guard rejections are zero.
4. No uninstalled-model routing failures in loop logs.

## P1: Canonical Assets Runnable
Objective: ensure repo-native assets execute without test-only scaffolding.

Work:
1. [x] Add CI integrity gate for model asset references.
   - landed in `tests/platform/test_model_asset_integrity.py`.
2. [x] Repair hard missing team/role assets that blocked canonical checks.
   - added missing roles in `model/core/roles/`.
   - added missing team `model/core/teams/product_owners.json`.
3. [x] Repair acceptance fixture outputs to satisfy architecture decision contract.
4. [~] Continue canonical role/team normalization for consistency and deduplication.
   - current state is executable and integrity-checked; cleanup remains.

Done when:
1. No missing role/team/seat links in `model/core/**`.
2. Loader/runtime execute canonical epics without `CardNotFound` for roles.

Verification:
1. `python -m pytest tests/platform/test_config_loader.py -q`
2. `python -m pytest tests/platform/test_model_asset_integrity.py -q`

## Code Review Attachment (2026-02-14)
Findings from `Agents/CodexReview.md` are attached to roadmap sections:
1. `P0-B`:
   - maintain strict guard contracts and keep deterministic reprompt paths.
2. `P1`:
   - integrity gate added and core asset linkage repaired.
3. `P2`:
   - acceptance fixture updated to emit architect decision JSON contract.
4. Cross-cutting follow-up:
   - evaluate whether architecture contract should also apply to `lead_architect` seats without destabilizing legacy fixtures.
   - reduce non-essential sandbox deploy attempts in acceptance flows to lower telemetry noise.

## P2: Acceptance Gate Uses Canonical Assets
Objective: stop proving success with synthetic fixtures only.

Work:
1. Add canonical-asset acceptance test that loads repo model assets directly.
2. Keep deterministic fixture test for engine behavior, but make it secondary.
3. Enforce chain validation in canonical acceptance:
   - role order
   - expected artifacts
   - guard terminal decision
   - all chain issues reach `DONE` in live acceptance

Done when:
1. Acceptance fails if `coder` stage is missing/replaced.
2. Acceptance fails on canonical asset inconsistency.

Verification:
1. `python -m pytest tests/live/test_system_acceptance_pipeline.py -q`
2. `python -m pytest tests/integration/test_system_acceptance_flow.py -q`

## P3: Boundary Enforcement (Maintain)
Objective: keep boundary protections active without broad cleanup churn.

Work:
1. Keep `scripts/check_volatility_boundaries.py` as pre-merge gate.
2. Add focused checks only when a new coupling bypass appears.

Verification:
1. `python scripts/check_volatility_boundaries.py`
2. `python -m pytest tests/platform/test_architecture_volatility_boundaries.py -q`

## Items Removed As No Longer Relevant
1. Legacy P0 volatility-shim retirement workstreams (already completed and merged).
2. `docs/DOCUMENTATION_MAP.md` workflow.
3. `docs/OrketArchitectureModel.md` as required architecture authority.
4. `workspace/observability/live_acceptance_loop.db` as primary trend DB path.

## Weekly Proof
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python scripts/run_live_acceptance_loop.py --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. Query latest batch in `.orket/durable/observability/live_acceptance_loop.db`.
