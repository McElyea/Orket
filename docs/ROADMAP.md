# Orket Roadmap (Active Only)

Last updated: 2026-02-14.

## North Star
Ship one canonical, reliable pipeline that passes this exact flow with deterministic guard governance:
1. `requirements_analyst`
2. `architect`
3. `coder`
4. `code_reviewer`
5. `integrity_guard`

If this flow is not mechanically proven with canonical assets and machine-readable guard contracts, we are not done.

## Operating Rules
1. Keep changes small and reversible.
2. No architecture pivots while stabilization work is active.
3. Every change must map to a failing or missing test.
4. Single owner per rule:
   - `Role + Skill + Dialect` define behavior, style, structure, and intent.
   - `Guards` enforce runtime correctness constraints.
   - `Guard Agent` validates only and never generates content.
5. Guard outcomes must be deterministic, machine-readable, and diagnosable from runtime artifacts.

## Current Priority Order
1. `P0 Highest`: Guard System Baseline (contract + loop control + ownership boundaries + hallucination guard).
2. `P1 High`: Security/consistency guard rollout using the same baseline contract.
3. `P2 Medium`: Prompt Engine optimization/promotion loop follow-ups.
4. `P3 Low`: Telemetry and tooling polish outside stabilization goals.

## P0: Guard System Baseline (Highest Priority)
Objective: land a minimal, enforceable guard core that prevents retry spirals and hallucination drift.

### P0-R1: Canonical Contract Layer
1. `P0-R1-S1` (completed 2026-02-14): define and enforce canonical `GuardContract` fields:
   - `result`, `violations`, `severity`, `fix_hint`, `terminal_failure`, `terminal_reason`.
2. `P0-R1-S2` (completed 2026-02-14): define canonical `Violation` fields:
   - `rule_id`, `code`, `message`, `location`, `severity`, `evidence`.
3. `P0-R1-S3` (completed 2026-02-14): define canonical loop-control contracts:
   - `LoopControl(max_retries, retry_backoff, escalation)`.
   - `TerminalReason(code, message)`.
4. `P0-R1-S4` (completed 2026-02-14): enforce severity aggregation rule globally:
   - `soft < strict`.
   - contract severity is max violation severity.
   - no violations => `severity=soft`.

### P0-R2: Runtime Loop Enforcement
1. `P0-R2-S1` (completed 2026-02-14): route runtime-verifier guarded-stage validation through Guard Agent return of `GuardContract`.
2. `P0-R2-S2` (completed 2026-02-14): enforce bounded retries with deterministic escalation on exceed for runtime-verifier guard failures.
3. `P0-R2-S3` (completed 2026-02-14): emit terminal guard outcomes as `terminal_failure` with structured `terminal_reason`.
4. `P0-R2-S4` (completed 2026-02-14): persist runtime guard artifacts (`guard_contract`, `guard_decision`) in verification evidence.

### P0-R3: Ownership Boundaries
1. `P0-R3-S1` (completed 2026-02-14): enforce prompt-level ownership in prompt resolution (`Role + Skill + Dialect` only).
2. `P0-R3-S2` (completed 2026-02-14): enforce runtime-level guard namespace in prompt overlays (`hallucination`, `security`, `consistency` only).
3. `P0-R3-S3` (completed 2026-02-14): reject duplicated/conflicting rule ownership at prompt-resolution validation time across prompt and runtime guard rule catalogs.
4. `P0-R3-S4` (completed 2026-02-14): harden Guard Agent as non-generative validator only.

### P0-R4: Hallucination Guard V1
1. `P0-R4-S1` (completed 2026-02-14): add canonical hallucination guard prompt injection layer.
2. `P0-R4-S2` (completed 2026-02-14): add explicit verification scope per run:
   - `workspace`, `provided_context`, `declared_interfaces`.
3. `P0-R4-S3`: implement checks for:
   - out-of-scope file references (completed 2026-02-14).
   - undeclared API/interface references (completed 2026-02-14).
   - missing context references (completed 2026-02-14).
   - invented details and contradictions.
4. `P0-R4-S4`: ship initial violation taxonomy with evidence fields:
   - `HALLUCINATION.FILE_NOT_FOUND`
   - `HALLUCINATION.API_NOT_DECLARED`
   - `HALLUCINATION.CONTEXT_NOT_PROVIDED`
   - `HALLUCINATION.INVENTED_DETAIL`
   - `HALLUCINATION.CONTRADICTION`
5. `P0-R4-S5`: escalate persistent repeats to `terminal_failure` using `HALLUCINATION_PERSISTENT`.

### P0 Exit Criteria
1. Guarded stages emit valid `GuardContract` artifacts.
2. Retry behavior is bounded and deterministic under repeated failures.
3. Hallucination guard blocks out-of-scope references with explicit evidence.
4. Canonical acceptance and live-loop reports expose guard-driven `terminal_failure` reasons without manual log archaeology.

### P0 Verification Targets
1. `python -m pytest tests/application/test_turn_executor_middleware.py -q`
2. `python -m pytest tests/application/test_orchestrator_epic.py -q`
3. `python -m pytest tests/application/test_execution_pipeline_session_status.py -q`
4. `python -m pytest tests/live/test_system_acceptance_pipeline.py -q`

## P1: Security and Consistency Guard Rollout
Objective: extend the P0 baseline to the other two guard domains without changing core contracts.

Remaining Slices:
1. `P1-S1`: implement Security Guard using canonical `GuardContract` and scope-aware checks.
2. `P1-S2`: implement Consistency Guard using canonical `GuardContract` and schema/style checks.
3. `P1-S3`: add guard rule cataloging and deterministic rule-id ownership checks.
4. `P1-S4`: publish guard-specific telemetry counters and failure reason distributions.

Exit Criteria:
1. All three guard domains (`hallucination`, `security`, `consistency`) share one contract path.
2. No duplicated rule ownership between prompt layers and runtime guard validators.
3. Runtime telemetry can attribute `terminal_failure` by guard domain and rule id.

## P2: Prompt Engine Optimization Follow-Ups
Objective: continue prompt optimization safely after guard baseline is stable.

Remaining Slices:
1. `P2-S1`: offline optimize workflow writes candidate versions only.
2. `P2-S2`: compare candidate vs stable on canonical acceptance and live-loop pattern reports.
3. `P2-S3`: gate promotion on explicit evidence thresholds and guard-failure deltas.

## P3: Architecture Boundaries and Maintenance
Objective: keep dependency direction and volatility boundaries green while guard work lands.

Recurring Verification:
1. `python scripts/check_dependency_direction.py`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest tests/platform/test_architecture_volatility_boundaries.py -q`

## Completed Programs (Archived)
1. Prompt Engine foundation/versioning/runtime attribution/tooling (`P0-F1` to `P0-R1`) is complete.
2. Stabilizer policy hardening (`P-1` scaffolder/dependency manager/runtime verifier/deployment planner) is complete.
3. Canonical asset and acceptance gate hardening (`P2`) is complete.
4. V1 model behavior stabilization and `terminal_failure` session semantics are complete.

## Weekly Proof
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. `python -m scripts.report_live_acceptance_patterns`
