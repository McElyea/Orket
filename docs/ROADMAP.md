# Orket Roadmap

Roadmap source of truth for active and upcoming work.  
Architecture authority: `docs/OrketArchitectureModel.md`.  
Last updated: 2026-02-11.

## Operating Rule
At handoff, update this file first:
1. Move completed bullets into `Completed`.
2. Rewrite `Remaining` with concrete next work.
3. Keep acceptance criteria measurable.

## Current Baseline
1. `python -m pytest tests/ -q` -> 211 passed.
2. `python -m pytest --collect-only -q` -> 211 collected.

## Open Phases

### P0. Correctness Hotfixes (Immediate)
Completed:
1. Full test baseline is green (211/211).
2. Fixed metrics timestamp correctness in `orket/hardware.py` (UTC ISO timestamp, removed `os.getlogin()` misuse).
3. Fixed verification fatal-path accounting in `orket/domain/verification.py`:
   - missing fixture now marks all scenarios failed
   - subprocess fatal exit now marks all scenarios failed
4. Added regression tests for missing fixture and fatal subprocess exit (`tests/test_verification_subprocess.py`).
5. Added metrics timestamp validity assertion in `tests/test_api.py`.

Remaining:
1. Add coverage for additional fatal verification branches (`parsed ok=false` path and generic exception fallback).

Acceptance:
1. `/v1/system/metrics` always returns a valid UTC timestamp field.
2. Verification result counts never under-report failures on fatal paths.
3. New tests cover both regression classes.

### P1. R2 API Decomposition Finalization
Completed:
1. Extracted significant API policy decisions into `ApiRuntimeStrategyNode`:
   - CORS parsing/defaults
   - API key policy
   - run-active invocation policy
   - clear-log path
   - metrics normalization
   - calendar window
   - explorer path/filter/sort
   - preview target/invocation
   - run-metrics workspace selection
   - sandbox workspace/pipeline creation
   - chat driver creation
   - websocket removal policy
   - engine/file-tools creation seams

Remaining:
1. Continue moving endpoint construction/wiring volatility from `orket/interfaces/api.py` to seams.
2. Reduce transport-layer churn and branch density in `orket/interfaces/api.py`.
3. Add focused tests for seam-driven endpoint parity (`preview`, `run-active` variants).

Acceptance:
1. API handlers are transport-focused (validation/status/serialization).
2. `orket/interfaces/api.py` shrinks in branch complexity and churn.
3. API regression suite remains green.

### P2. R3 Orchestrator Decomposition Completion
Completed:
1. Extracted loop policy seams into `OrchestrationLoopPolicyNode`:
   - concurrency limit
   - max iterations
   - context window
   - review-turn detection
   - turn status selection
   - role order policy
   - missing-seat status

Remaining:
1. Extract failure-path lifecycle policy from `_handle_failure` into evaluator/loop seams.
2. Extract remaining `_execute_issue_turn` policy branches (sandbox-trigger gating and review promotion conditions).
3. Keep core `execute_epic` loop shape stable while reducing direct policy branching.

Acceptance:
1. `execute_epic` behavior remains equivalent under current suite.
2. Policy changes happen in decision nodes without loop-shape edits.

### P3. Async Safety and Throughput
Completed:
1. Verification is subprocess-isolated for fixture execution.

Remaining:
1. Remove event-loop blocking sync verification call in `Orchestrator.verify_issue` (use async bridge/thread strategy).
2. Reduce synchronous subprocess impact in `/v1/system/metrics` path (cache or periodic sampling strategy).
3. Add concurrency/load tests validating no starvation on verification-heavy runs.

Acceptance:
1. No synchronous heavy calls in async hot paths.
2. Throughput under parallel turns remains stable.

### P4. Observability and Operational Hygiene
Completed:
1. Event logging infrastructure exists and is consumed in core flows.

Remaining:
1. Replace runtime `print` calls in hot paths (`api`, `orchestrator`, `execution_pipeline`) with structured logging.
2. Add warning telemetry for currently suppressed operational failures (`clear-logs` path).
3. Standardize run/session correlation IDs in logs for API -> orchestrator traceability.

Acceptance:
1. Runtime logs are structured, machine-parseable, and correlated.
2. Operational failures are observable without reading stdout.

### P5. Tool Boundary Reduction (R1 Completion)
Completed:
1. `ToolBox` is strategy-composed and mostly forwarding-oriented.

Remaining:
1. Audit `orket/tools.py` for residual non-forwarding business/process logic.
2. Move any residual mixed responsibility into tool-family/runtime seams.
3. Verify backward compatibility for existing tool-call patterns.

Acceptance:
1. `ToolBox` remains composition/compat shell only.
2. `tests/test_toolbox_refactor.py` and `tests/test_decision_nodes_planner.py` remain green.

### P6. Verification and Quality Gates
Completed:
1. Baseline suite is green.

Remaining:
1. Add regression tests for all critical findings in `Agents/CodexReview.md`.
2. Add CI gate for line-ending normalization policy to reduce noisy diffs.
3. Add API contract tests for route parameters currently at risk of drift.

Acceptance:
1. Critical regression classes are guarded by tests.
2. CI blocks known drift patterns before merge.

## Done Workflow
Use `Exists -> Working -> Done`:
1. Exists: defined in this roadmap with measurable acceptance.
2. Working: has explicit `Completed` and `Remaining` bullets.
3. Done: acceptance verified, then remove from roadmap and add one `CHANGELOG.md` entry.
