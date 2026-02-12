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
1. `python -m pytest tests/ -q` -> 230 passed.
2. `python -m pytest --collect-only -q` -> 230 collected.

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
   - session detail missing-session 404 behavior
   - session snapshot missing-session 404 behavior
   - sandboxes list/stop route behavior
   - runs list/backlog delegation behavior
4. Moved additional route invocation wiring into `ApiRuntimeStrategyNode`:
   - `/v1/runs`
   - `/v1/runs/{session_id}/backlog`
   - `/v1/sessions/{session_id}`
   - `/v1/sessions/{session_id}/snapshot`
5. Added runtime policy and error-path parity tests for those routes (unsupported method guards included).
6. Moved sandbox route invocation wiring into `ApiRuntimeStrategyNode`:
   - `/v1/sandboxes`
   - `/v1/sandboxes/{sandbox_id}/stop`
7. Added runtime policy and error-path parity tests for sandbox route invocation behavior.

Remaining:
1. Continue moving endpoint construction/wiring volatility from `orket/interfaces/api.py` to seams.
2. Reduce transport-layer churn and branch density in `orket/interfaces/api.py`.
3. Add parity tests for remaining endpoint behaviors with conditional branches (error/empty-state cases).

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
3. Extracted additional success/failure lifecycle policy into `EvaluatorNode`:
   - `success_post_actions` (sandbox trigger + next-status policy)
   - `failure_event_name` (action -> event routing policy)
4. Extracted failure-message composition policy into `EvaluatorNode`:
   - governance violation message
   - catastrophic failure message
   - unexpected action message
   - retry failure message
5. Extracted failure exception-type selection into `EvaluatorNode`:
   - `failure_exception_class(action)` now controls raised exception class for governance/catastrophic/retry/unknown actions.
6. Extracted remaining success-branch policy checks in `_execute_issue_turn` into `EvaluatorNode`:
   - `should_trigger_sandbox(success_actions)`
   - `next_status_after_success(success_actions)`

Remaining:
1. Keep core `execute_epic` loop shape stable while reducing direct policy branching.

Acceptance:
1. `execute_epic` behavior remains equivalent under current suite.
2. Policy changes happen in decision nodes without loop-shape edits.

### P3. Async Safety and Throughput
Completed:
1. Verification is subprocess-isolated for fixture execution.
2. Removed event-loop blocking verification call in `Orchestrator.verify_issue` by using `asyncio.to_thread`.
3. Reduced synchronous metrics pressure by adding TTL cache for VRAM probes (`ORKET_METRICS_VRAM_CACHE_SEC`).
4. Added tests for async verification path and metrics cache behavior.
5. Added verification-heavy async concurrency coverage (`tests/test_orchestrator_verification_async.py`) to confirm parallel `verify_issue` calls do not starve the event loop.

Remaining:
1. Evaluate moving metrics sampling to background task if API latency remains high under load.

Acceptance:
1. No synchronous heavy calls in async hot paths.
2. Throughput under parallel turns remains stable.

### P4. Observability and Operational Hygiene
Completed:
1. Event logging infrastructure exists and is consumed in core flows.
2. Added warning telemetry for `clear-logs` suppression path.
3. Replaced hot-path `print` calls in `api.py` and key `orchestrator.py` flow points with `log_event`.
4. Replaced `execution_pipeline.py` phase/status prints with structured `log_event` calls.
5. Replaced additional runtime/service `print` calls with structured logging:
   - `runtime/config_loader.py` validation failures
   - `domain/failure_reporter.py` report-created notice
   - `services/gitea_webhook_handler.py` sandbox deploy/failure notices
6. Standardized session/run correlation payloads across API and orchestrator logs:
   - API now emits `session_id` for run metrics/backlog/session detail/session snapshot routes.
   - Orchestrator now emits `run_id` in dispatch/failure events and threads it into verification/sandbox deployment events when available.
7. Added API regression coverage for correlation log payloads on session-scoped endpoints (`tests/test_api.py`).
8. Replaced additional high-frequency runtime `print` calls with structured logging:
   - `llm.py` retry warnings (`model_timeout_retry`, `model_connection_retry`)
   - `logging.py` subscriber failure handling (`logging_subscriber_failed`)
   - `driver.py` process-failure fallback (`driver_process_failed`)

Remaining:
1. Replace remaining non-test `print` usage in non-core command/bootstrap flows (CLI/discovery/setup scripts) where structured logging is preferable.

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
2. Added repo-level line-ending policy and CI normalization gate:
   - `.gitattributes` sets LF as default with CRLF exceptions for `*.bat`/`*.cmd`.
   - `quality.yml` now fails if `git add --renormalize .` produces staged drift.

Remaining:
1. Add regression tests for all critical findings in `Agents/CodexReview.md`.
2. Add API contract tests for route parameters currently at risk of drift.

Acceptance:
1. Critical regression classes are guarded by tests.
2. CI blocks known drift patterns before merge.

## Done Workflow
Use `Exists -> Working -> Done`:
1. Exists: defined in this roadmap with measurable acceptance.
2. Working: has explicit `Completed` and `Remaining` bullets.
3. Done: acceptance verified, then remove from roadmap and add one `CHANGELOG.md` entry.
