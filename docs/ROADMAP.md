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
4. Prefer stage/seat contract hardening over broad refactors.
5. Keep governance mechanical and explicit in runtime evidence.

## Current Priority Order
1. `V2 Medium Volatility`: stage policy expansion (`P-1` follow-through).
2. `V3 Medium-Low Volatility`: canonical asset alignment and acceptance gate hardening.
3. `V4 Low Volatility`: boundary enforcement and maintenance checks.

## V1: High Volatility (Model Behavior) - Complete
Objective: reduce run-to-run behavioral drift that blocks the canonical chain.

Completed Work:
1. First-turn contract hardening now enforces deterministic required write paths for `requirements_analyst`, `architect`, and `coder`.
2. Turn correction now uses a bounded single corrective reprompt with unified contract diagnostics to reduce reprompt cascades.
3. Guard cascade reduction is active: non-final guard turns are `done`-only; final guard review remains explicit.
4. Live-loop and pattern reports now classify completion by canonical `chain_complete` signal.

Completion Evidence:
1. Batch `20260214T211238Z-84e26cb2`: 2/2 canonical successes, `turn_non_progress=0`, `done_chain_mismatch=0`.
2. Batch `20260214T211314Z-618a3380`: 2/2 canonical successes, `turn_non_progress=0`, `done_chain_mismatch=0`.
3. Baseline chain completion across both consecutive batches: 100%.

## V2: Medium Volatility (Stage Policy and Stabilizers)
Objective: complete and harden `P-1` stabilizers as deterministic stage contracts.

Current State:
1. Scaffolder, dependency manager, runtime verifier, and deployment planner base slices are landed.
2. Runtime verifier includes command-matrix hooks and runtime report artifact output.
3. Session semantics now distinguish `done` from `terminal_failure`.

Remaining Work:
1. Expand dependency manager from baseline manifest generation to policy-driven pinned/dev dependency policy.
2. Expand runtime verifier command policy by stack profile with clear defaults and failure classification.
3. Integrate deployment planner expectations directly into runtime verification policy for all relevant stacks.
4. Add stricter ownership enforcement paths for dependency/deployment artifacts where policy is enabled.

Exit Criteria:
1. Stabilizer stages are fully policy-driven and test-covered.
2. Runtime verifier failures are clearly attributed by stage and command source in artifacts/telemetry.
3. `terminal_failure` runs are diagnosable without manual log archaeology.

Verification:
1. `python -m pytest tests/application/test_orchestrator_epic.py -q`
2. `python -m pytest tests/application/test_runtime_verifier_service.py -q`
3. `python -m pytest tests/adapters/test_sandbox_compose_generation.py -q`

## V3: Medium-Low Volatility (Canonical Assets and Acceptance Gate)
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

## V4: Low Volatility (Architecture Boundaries and Maintenance)
Objective: hold core architectural boundaries while stabilization work continues.

Active Work:
1. Keep dependency direction and volatility boundary checks green.
2. Add only focused guards when new coupling bypasses appear.

Verification:
1. `python scripts/check_dependency_direction.py`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest tests/platform/test_architecture_volatility_boundaries.py -q`

## Weekly Proof
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. `python -m scripts.report_live_acceptance_patterns`
