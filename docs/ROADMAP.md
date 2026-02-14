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
1. `P1 Highest`: Stage policy and stabilizer follow-through (`P-1B` to `P-1D` hardening).
2. `P2 High`: Canonical asset alignment and acceptance gate hardening.
3. `P3 Medium`: Architecture boundary enforcement and maintenance checks.
4. `P4 Low`: Prompt Engine enhancement follow-ups (only if regressions emerge).

## P0: Prompt Engine Program (Highest Priority)
Objective: make prompts first-class, versioned, inspectable assets with deterministic runtime resolution.

### Completed Milestones
1. `P0-F1`: Prompt resolver foundation is landed and test-covered.
2. `P0-F2`: Prompt versioning/governance metadata and selection policy are landed.
3. `P0-F3`: Runtime policy attribution is landed in artifacts and live-loop reporting.
4. `P0-R1`: Prompt tooling + CI validation workflow is landed (`orket-prompts` commands + CI validator gate).

### Status
`P0` is complete.

## P1: Stage Policy and Stabilizer Follow-Through
Objective: complete and harden `P-1` stabilizers as deterministic policy contracts.

Remaining Slices:
1. `P1-S1` (completed): expand dependency manager to policy-driven pinned/dev dependency sets.
2. `P1-S2` (completed): expand runtime verifier command policy by stack profile and failure class.
3. `P1-S3`: integrate deployment planner expectations into verifier policy for all stacks.
4. `P1-S4`: enforce ownership boundaries for dependency/deployment artifacts when policy-enabled.

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

Remaining Slices:
1. `P2-S1`: finish remaining role/team asset normalization and consistency checks.
2. `P2-S2`: strengthen canonical acceptance assertions for artifact and stage outcomes.
3. `P2-S3`: keep fixture acceptance tests secondary to canonical-asset behavior.

Exit Criteria:
1. Canonical acceptance fails on chain breakage or asset inconsistency.
2. No hidden test-only scaffolding is required for canonical flow viability.

Verification:
1. `python -m pytest tests/platform/test_model_asset_integrity.py -q`
2. `python -m pytest tests/live/test_system_acceptance_pipeline.py -q`
3. `python -m pytest tests/integration/test_system_acceptance_flow.py -q`

## P3: Architecture Boundaries and Maintenance
Objective: hold core architectural boundaries while stabilization work continues.

Remaining Slices:
1. `P3-S1`: keep dependency direction and volatility boundary checks green.
2. `P3-S2`: add focused guards only when new coupling bypasses appear.

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
