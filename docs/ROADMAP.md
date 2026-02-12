# Orket Roadmap

Roadmap source of truth for active and upcoming work.  
Architecture authority: `docs/OrketArchitectureModel.md`.  
Last updated: 2026-02-12.

## Operating Rule
At handoff, update this file first:
1. Move completed bullets into `Completed`.
2. Rewrite `Remaining` with concrete next work.
3. Keep acceptance criteria measurable.

## Current Baseline
1. `python -m pytest tests/ -q` -> 250 passed.
2. `python -m pytest --collect-only -q` -> 250 collected.

## Open Chunk Gates

Progression rule: move only by chunk-gate pass/fail criteria, not by dates or time windows.

### P-1 Chunk Gate: OrketLabs Experiment
Completed:
1. Experiment scope defined (no code movement yet).

Remaining:
1. Create `c:\Source\OrketLabs` as an experiment-only workspace; keep `c:\Source\Orket` as source of truth.
2. Implement one vertical slice only: run-session flow (`API entry -> orchestration kickoff -> status/log outputs`).
3. Use Labs layering: `flows`, `nodes`, `seams`, `adapters/orket`.
4. Reuse Orket via import/adapter first; avoid copying code unless required for bootstrap.
5. Exclude non-goals for phase 1: DB migrations, webhook automation, sandbox deployment stack, UI.
6. Add parity tests for chosen slice plus one seam-swap test proving policy replacement without flow rewrites.
7. Record volatility metrics for the slice (flow edits vs seam/adapter edits).
8. Decide outcome after slice: adopt pattern incrementally in Orket, run second slice, or retire experiment.

Acceptance:
1. One end-to-end slice runs in Labs with behavior parity on selected contracts.
2. Policy changes happen mainly in `seams`/`adapters`, not `flows`.
3. Orket production code remains unchanged by experiment bootstrap.

### P0 Chunk Gate: Correctness Hotfixes
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

### P1 Chunk Gate: R2 API Decomposition Finalization
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
8. Added conditional error-path API parity tests:
   - `/v1/system/read` missing-file 404
   - `/v1/system/save` permission-denied 403
   - `/v1/system/preview-asset` unsupported-mode 400
9. Reduced repeated API transport branching by introducing shared async invocation helper in `orket/interfaces/api.py` for seam-resolved method dispatch/guarding.
10. Extended invocation helper usage to additional transport paths (sandbox logs guard path) to reduce duplicated method-resolution branches.
11. Moved `/v1/system/read` and `/v1/system/save` invocation wiring into `ApiRuntimeStrategyNode` with runtime-policy parity/error-path tests.
12. Moved `/v1/sandboxes/{sandbox_id}/logs` invocation wiring into `ApiRuntimeStrategyNode`:
   - added `resolve_sandbox_logs_invocation(sandbox_id, service)` seam
   - transport now performs sync dispatch via invocation helper
13. Added sandbox logs runtime-invocation parity/error-path tests:
   - custom invocation method dispatch path
   - unsupported runtime method 400 guard

Remaining:
1. Continue moving endpoint construction/wiring volatility from `orket/interfaces/api.py` to seams.
2. Continue reducing transport-layer churn and branch density in `orket/interfaces/api.py`.
3. Add parity tests for remaining endpoint behaviors with conditional branches (error/empty-state cases).

Acceptance:
1. API handlers are transport-focused (validation/status/serialization).
2. `orket/interfaces/api.py` shrinks in branch complexity and churn.
3. API regression suite remains green.

### P2 Chunk Gate: R3 Orchestrator Decomposition Completion
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
7. Extracted execute-loop empty-candidate/exhaustion decisions into loop policy seams:
   - `no_candidate_outcome(backlog)`
   - `should_raise_exhaustion(iteration_count, max_iterations, backlog)`
   with backward-compatible fallback behavior in orchestrator.

Remaining:
1. None.

Acceptance:
1. `execute_epic` behavior remains equivalent under current suite.
2. Policy changes happen in decision nodes without loop-shape edits.

### P3 Chunk Gate: Async Safety and Throughput
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

### P4 Chunk Gate: Observability and Operational Hygiene
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
9. Replaced additional non-interactive workflow prints with structured logging:
   - `agents/agent.py` config-asset fallback notices
   - `preview.py` org/role load fallback notices
   - `domain/reconciler.py` reconciliation progress/warnings
   - `organization_loop.py` loop lifecycle/skip warnings
   - `discovery.py` reconciliation failure warning
10. Replaced additional runtime `print` in `tool_families/vision.py` pipeline-load path with structured telemetry.
11. Added print-usage policy guard (`tests/test_runtime_print_policy.py`) with explicit allowlist for intentional interactive/stdout cases.

Remaining:
1. None.

Acceptance:
1. Runtime logs are structured, machine-parseable, and correlated.
2. Operational failures are observable without reading stdout.

### P5 Chunk Gate: Tool Boundary Reduction (R1 Completion)
Completed:
1. `ToolBox` is strategy-composed and mostly forwarding-oriented.
2. Audited `orket/tools.py` for residual business/process logic; confirmed forwarding-only shell behavior.
3. Added forwarding delegation regression coverage in `tests/test_toolbox_refactor.py`.
4. Verified backward compatibility by keeping toolbox/refactor suites green.

Remaining:
1. None.

Acceptance:
1. `ToolBox` remains composition/compat shell only.
2. `tests/test_toolbox_refactor.py` and `tests/test_decision_nodes_planner.py` remain green.

### P6 Chunk Gate: Verification and Quality Gates
Completed:
1. Baseline suite is green.
2. Added repo-level line-ending policy and CI normalization gate:
   - `.gitattributes` sets LF as default with CRLF exceptions for `*.bat`/`*.cmd`.
   - `quality.yml` now fails if `git add --renormalize .` produces staged drift.
3. Added API contract coverage for route-parameter drift risks:
   - `/v1/system/board` default `dept=core`
   - `/v1/sandboxes/{sandbox_id}/logs` optional `service` propagation (`None` when omitted)
4. Closed regression coverage for all critical findings in `Agents/CodexReview.md`:
   - metrics timestamp validity
   - board `dept` propagation
   - fatal verification accounting
   - async verification non-blocking path

Remaining:
1. None.

Acceptance:
1. Critical regression classes are guarded by tests.
2. CI blocks known drift patterns before merge.

## Done Workflow
Use `Exists -> Working -> Done`:
1. Exists: defined in this roadmap with measurable acceptance.
2. Working: has explicit `Completed` and `Remaining` bullets.
3. Done: acceptance verified, then remove from roadmap and add one `CHANGELOG.md` entry.
