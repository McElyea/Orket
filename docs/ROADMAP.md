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
1. `python -m pytest tests/ -q` -> 222 passed.
2. `python -m pytest --collect-only -q` -> 222 collected.

## Open Phases

### P0. Correctness Hotfixes (Immediate)
Completed:
1. Full test baseline is green (222/222).
2. Fixed metrics timestamp correctness in `orket/hardware.py` (UTC ISO timestamp, removed `os.getlogin()` misuse).
3. Fixed verification fatal-path accounting in `orket/domain/verification.py`:
   - missing fixture now marks all scenarios failed
   - subprocess fatal exit now marks all scenarios failed
4. Added regression tests for missing fixture and fatal subprocess exit (`tests/test_verification_subprocess.py`).
5. Added metrics timestamp validity assertion in `tests/test_api.py`.
6. Added coverage for additional fatal verification branches:
   - parsed `ok=false` path
   - generic `OSError` fallback path

Remaining:
1. None.

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
2. Fixed `/v1/system/board` contract to honor `dept` via runtime seam.
3. Added seam-driven endpoint parity tests:
   - board `dept` propagation
   - preview invocation wiring
   - run-active invocation wiring
   - run-active unsupported method behavior
   - run-metrics workspace seam usage
   - sandbox logs pipeline-factory seam usage

Remaining:
1. Continue moving endpoint construction/wiring volatility from `orket/interfaces/api.py` to seams.
2. Reduce transport-layer churn and branch density in `orket/interfaces/api.py`.
3. Add parity tests for additional endpoints (`sessions`, `snapshot`, `sandboxes list/stop`) where seams exist.

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
2. Extracted failure-path status/cancel policy to `EvaluatorNode`:
   - `status_for_failure_action`
   - `should_cancel_session`

Remaining:
1. Extract remaining `_execute_issue_turn` policy branches (sandbox-trigger gating and review promotion conditions).
2. Extract failure logging/event policy shape from `_handle_failure` into evaluator/loop seams.
3. Keep core `execute_epic` loop shape stable while reducing direct policy branching.

Acceptance:
1. `execute_epic` behavior remains equivalent under current suite.
2. Policy changes happen in decision nodes without loop-shape edits.

### P3. Async Safety and Throughput
Completed:
1. Verification is subprocess-isolated for fixture execution.
2. Removed event-loop blocking verification call in `Orchestrator.verify_issue` by using `asyncio.to_thread`.
3. Reduced synchronous metrics pressure by adding TTL cache for VRAM probes (`ORKET_METRICS_VRAM_CACHE_SEC`).
4. Added tests for async verification path and metrics cache behavior.

Remaining:
1. Add concurrency/load tests validating no starvation on verification-heavy runs.
2. Evaluate moving metrics sampling to background task if API latency remains high under load.

Acceptance:
1. No synchronous heavy calls in async hot paths.
2. Throughput under parallel turns remains stable.

### P4. Observability and Operational Hygiene
Completed:
1. Event logging infrastructure exists and is consumed in core flows.
2. Added warning telemetry for `clear-logs` suppression path.
3. Replaced hot-path `print` calls in `api.py` and key `orchestrator.py` flow points with `log_event`.

Remaining:
1. Replace remaining runtime `print` calls in `execution_pipeline.py` and other runtime hot paths.
2. Standardize run/session correlation IDs in logs for API -> orchestrator traceability.

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
