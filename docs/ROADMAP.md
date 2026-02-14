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

## Operating Rules
1. Keep changes small and reversible.
2. No architecture pivots while stabilization work is active.
3. Every change must map to a failing or missing test.
4. Prefer deterministic contracts and policy assets over implicit prompt behavior.
5. Keep governance mechanical and explicit in runtime evidence.

## Current Priority Order
1. `P0 Highest`: Prompt Engine program (governable prompt assets and deterministic prompt resolution).
2. `P1 High`: Stage policy and stabilizer follow-through (`P-1B` to `P-1D` hardening).
3. `P2 Medium`: Canonical asset alignment and acceptance gate hardening.
4. `P3 Low`: Architecture boundary enforcement and maintenance checks.

## P0: Prompt Engine Program (Highest Priority)
Objective: make prompts first-class, versioned, inspectable assets with deterministic runtime resolution.

### Phase 1 (Completed): Prompt Resolver Foundation
Goal: introduce deterministic prompt composition without rewriting orchestration.

Scope:
1. Add prompt metadata contract for role and dialect assets, compatible with existing `RoleConfig` and `DialectConfig`.
2. Add a `PromptResolver` service that composes:
   role prompt + dialect constraints + stage/seat contracts + context profile + guard overlays.
3. Keep existing `PromptCompiler` behavior as fallback while resolver is introduced behind feature policy.
4. Emit prompt provenance in turn telemetry/artifacts: `prompt_id`, `prompt_version`, `prompt_checksum`, `resolver_policy`.
5. Add schema and reference validation for prompt assets in CI.

Completed Slices:
1. `P0-F1-S1`: Prompt metadata schema fields and validation checks for role/dialect assets.
2. `P0-F1-S2`: Deterministic resolver API and precedence rules.
3. `P0-F1-S3`: Resolver integration path with compiler fallback policy.
4. `P0-F1-S4`: Prompt provenance and prompt-layer observability in turn artifacts/checkpoints.
5. `P0-F1-S5`: Regression coverage across orchestrator, turn executor, acceptance, and asset integrity tests.

Exit Criteria:
1. Resolver can deterministically reproduce current canonical prompt behavior for baseline roles.
2. Prompt provenance is present for every turn in observability artifacts.
3. Canonical acceptance remains green with resolver enabled.
4. Validation fails on malformed prompt metadata or broken references.

Verification:
1. `python -m pytest tests/application/test_turn_executor_middleware.py -q`
2. `python -m pytest tests/application/test_orchestrator_epic.py -q`
3. `python -m pytest tests/live/test_system_acceptance_pipeline.py -q`
4. `python -m pytest tests/platform/test_model_asset_integrity.py -q`

### Phase 2 (Completed): Prompt Versioning and Governance Lifecycle
Goal: make prompt change control explicit and auditable.

Scope:
1. Add status lifecycle: `draft`, `candidate`, `canary`, `stable`, `deprecated`.
2. Add semantic version policy with lineage and changelog metadata.
3. Add selection policy support: `stable`, `canary`, `exact`.
4. Add governance checks so production selection resolves only approved versions.

Concrete Slices:
1. `P0-F2-S1` (completed): add resolver selection policy evaluation (`stable/canary/exact`) with strict enforcement hooks and tests.
2. `P0-F2-S2` (completed): enforce production default selection policy (`stable`, strict) through orchestrator/runtime process rules.
3. `P0-F2-S3` (completed): add metadata lineage/changelog fields and validator checks for version progression.
4. `P0-F2-S4` (completed): add rollback test proving one metadata change can restore prior stable prompt version.

Exit Criteria:
1. Prompt selection policy is deterministic and test-covered.
2. Production path resolves approved/stable prompts by default.
3. Rollback to prior stable prompt is one metadata change.

### Phase 3 (Completed): Runtime Policy Integration
Goal: move volatile prompt behavior into explicit policy assets.

Scope:
1. Add context profiles and guard overlays as explicit resolver inputs.
2. Bind seat/stage contracts to resolver policies (instead of ad-hoc prompt edits).
3. Integrate resolver policy decisions into run artifacts and live-loop analysis.

Concrete Slices:
1. `P0-F3-S1` (completed): pass seat/stage contract overlays (`required_action_tools`, `required_statuses`, `required_read_paths`, `required_write_paths`, `stage_gate_mode`) into resolver context.
2. `P0-F3-S2` (completed): emit resolver selection policy details in run-level reporting and live-loop summaries.
3. `P0-F3-S3` (completed): add acceptance assertions proving seat/stage policy deltas are attributable to resolver policy metadata.

Exit Criteria:
1. Prompt behavior shifts are attributable to policy version changes.
2. Guard/stage behavior changes no longer require direct orchestration rewrites.

### Phase 4: Prompt Tooling (CLI + CI Workflow)
Goal: make prompt operations contributor-friendly and auditable.

Scope:
1. Add `orket-prompts` CLI commands: `list`, `show`, `diff`, `validate`, `resolve`, `new`, `promote`, `deprecate`.
2. Add CI checks for schema validity, reference validity, and placeholder consistency.
3. Add canary workflow for prompt rollout by model/team/epic.

Exit Criteria:
1. Prompt review and promotion are executable through CLI + git workflow.
2. CI blocks invalid prompt definitions before merge.

### Phase 5: Prompt Optimization Loop (Offline)
Goal: add controlled optimization, not in-run self-rewrite.

Scope:
1. Add offline `optimize` workflow that writes candidate prompt versions.
2. Compare candidate vs stable on canonical acceptance metrics and failure-pattern reports.
3. Require explicit promotion after evidence passes thresholds.

Exit Criteria:
1. Optimization can propose prompt upgrades without touching runtime orchestration code.
2. No runtime self-modifying prompts are required.

## P1: Stage Policy and Stabilizer Follow-Through
Objective: complete and harden `P-1` stabilizers as deterministic policy contracts.

Remaining Work:
1. Expand dependency manager from baseline manifest generation to policy-driven pinned/dev dependency policy.
2. Expand runtime verifier command policy by stack profile with clear defaults and failure classification.
3. Integrate deployment planner expectations directly into runtime verification policy for all relevant stacks.
4. Add stricter ownership enforcement paths for dependency/deployment artifacts where policy is enabled.

Exit Criteria:
1. Stabilizer stages are fully policy-driven and test-covered.
2. Runtime verifier failures are clearly attributed by stage and command source.
3. `terminal_failure` runs are diagnosable without manual log archaeology.

Verification:
1. `python -m pytest tests/application/test_orchestrator_epic.py -q`
2. `python -m pytest tests/application/test_runtime_verifier_service.py -q`
3. `python -m pytest tests/adapters/test_sandbox_compose_generation.py -q`

## P2: Canonical Assets and Acceptance Gate
Objective: keep success proof tied to repo-native assets and canonical contracts.

Active Work:
1. Continue role/team asset normalization where inconsistencies remain.
2. Strengthen canonical acceptance assertions for artifacts and stage outcomes.
3. Keep fixture acceptance tests secondary to canonical-asset acceptance behavior.

Exit Criteria:
1. Canonical acceptance fails on chain breakage or asset inconsistency.
2. No hidden test-only scaffolding is required for canonical flow viability.

Verification:
1. `python -m pytest tests/platform/test_model_asset_integrity.py -q`
2. `python -m pytest tests/live/test_system_acceptance_pipeline.py -q`
3. `python -m pytest tests/integration/test_system_acceptance_flow.py -q`

## P3: Architecture Boundaries and Maintenance
Objective: hold core architectural boundaries while stabilization work continues.

Active Work:
1. Keep dependency direction and volatility boundary checks green.
2. Add only focused guards when new coupling bypasses appear.

Verification:
1. `python scripts/check_dependency_direction.py`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest tests/platform/test_architecture_volatility_boundaries.py -q`

## Completed: V1 Model Behavior Stabilization
Summary:
1. First-turn contract hardening now enforces deterministic required write paths for key seats.
2. Turn correction now uses bounded single corrective reprompt with unified diagnostics.
3. Guard cascade reduction is active with explicit final-review guard behavior.
4. Live-loop and pattern reports classify completion by canonical `chain_complete`.

Completion Evidence:
1. Batch `20260214T211238Z-84e26cb2`: 2/2 canonical successes, `turn_non_progress=0`, `done_chain_mismatch=0`.
2. Batch `20260214T211314Z-618a3380`: 2/2 canonical successes, `turn_non_progress=0`, `done_chain_mismatch=0`.

## Weekly Proof
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. `python -m scripts.report_live_acceptance_patterns`
