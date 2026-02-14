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

## Current Status Snapshot
1. `P0 Data-Driven Behavior Recovery Loop`: Active.
2. `P1 Canonical Assets Runnable`: In progress.
3. `P2 Acceptance Gate Uses Canonical Assets`: In progress.
4. `P3 Boundary Enforcement`: Guardrail mode (maintain only).
5. `P4 Documentation Reset`: Completed for current baseline.

## Operating Rules
1. Simple over clever.
2. No broad refactors while recovery work is active.
3. Fix only what blocks the acceptance contract.
4. Every change must be tied to a failing or missing test.

## P0: Data-Driven Behavior Recovery Loop
Objective: use run evidence to systematically improve weak model behavior and raise canonical completion rate.

Why this is P0:
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

P0 exit criteria:
1. Baseline models achieve >= 80% full-chain completion for two consecutive batches.
2. `turn_non_progress` is < 5% overall and < 10% for any single role in baseline set.
3. Empty-rationale guard rejections are zero.
4. No uninstalled-model routing failures in loop logs.

## P1: Canonical Assets Runnable
Objective: ensure repo-native assets execute without test-only scaffolding.

Work:
1. Ensure canonical role files exist in `model/core/roles/` for required teams.
2. Repair team-role references in `model/core/teams/*.json`.
3. Repair epic-team-seat references in `model/core/epics/*.json`.
4. Add CI integrity gate for model asset references.

Done when:
1. No missing role/team/seat links in `model/core/**`.
2. Loader/runtime execute canonical epics without `CardNotFound` for roles.

Verification:
1. `python -m pytest tests/platform/test_config_loader.py -q`
2. `python -m pytest tests/platform/test_model_asset_integrity.py -q`

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
