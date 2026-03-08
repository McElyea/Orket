# OBT03082026 Implementation Plan

Last updated: 2026-03-08  
Status: Archived  
Owner: Orket Core

## Purpose

Convert the validated findings from `orket_behavioral_truth_review_v2.docx` into an active remediation lane that improves truthful behavior, truthful verification, and authority hygiene without broad refactoring.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/projects/archive/techdebt/OBT03082026/orket_behavioral_truth_review_v2.docx`
6. Current live repository state validated on 2026-03-08

## Current-State Validation Summary

Validated as still open:
1. `F1` quant-sweep nightly still presents a dry-run plus handcrafted perfect KPI artifact as a nightly KPI gate.
2. `F2` `AsyncExecutorService.run_coroutine_blocking()` still blocks on a worker-thread `asyncio.run(...)`, and current async structural-change paths still call sync `AsyncFileTools` methods.
3. `F3` `_load_engine_configs()` still contains dead `hasattr` guards after explicit initialization in `__init__`.
4. `F4` `log_event()` still performs synchronous file writes and repeated path setup on every call.
5. `F6` `OrganizationLoop.run_forever()` still does synchronous scan work without a guaranteed yield on the hot path.
6. `F7` `_logger` is still configured but bypassed by `log_event()`.
7. `F8` nightly memory comparison is still an identity-fixture smoke step and still needs truthful naming.
8. `F9` `ReviewRunService.run_pr()` still performs two full PR snapshot loads in `code_only` mode.
9. `F11` `halt_session` still returns `ok: true` even when the session id does not exist.
10. `F12` settings/preferences path resolution still creates config directories as import-time side effects.
11. `F13` `load_user_preferences()` still runs legacy migration work unconditionally on cold start.
12. `F14` legacy `log_event(level, component, event, payload)` still drops severity into the JSON payload instead of routing by level.
13. `F15` strict JSON parsing still uses a brace-position guard that overstates validation.
14. `F16` conversational provider failures are still swallowed without any logging signal.
15. `F17` structural-change errors still receive appended `Strategic Insight` narration.

Validated as stale or already reduced enough to stay out of scope for this cycle:
1. `F5` is not an active FastAPI event-loop blocker in the current authoritative route because `/system/metrics` already calls `get_metrics_snapshot()` via `asyncio.to_thread(...)`.
2. `F10` is stale as written because `ReviewRunService.run_diff()` is synchronous in the current tree rather than an async API path.

## Scope

In scope:
1. Truthful CI labeling and gating for the quant-sweep nightly lane.
2. Async/sync boundary safety for the current structural-change path and its shared executor bridge.
3. Logging truth and severity routing in the current unified logging surface.
4. Organization-loop fairness on the active hot path.
5. PR snapshot loading efficiency on the current review-run path.
6. Session halt truthfulness in the active API path.
7. Settings/preferences path and migration behavior.
8. Driver truth-surface cleanups for strict parsing, swallowed conversation failures, and structural-change error narration.
9. Roadmap and cycle-plan updates required to track the lane truthfully.

Out of scope:
1. Turning the nightly quant sweep into a live provider-backed KPI gate if CI infrastructure is not already prepared for real model execution.
2. Broad rewrite of the logging subsystem beyond the behavior needed to eliminate the validated truth gaps.
3. Refactoring historical or archived docs outside this active cycle.
4. Treating stale findings `F5` and `F10` as active defects without new current-tree evidence.

## Success Criteria

1. The quant-sweep nightly workflow no longer claims to enforce real KPIs from a dry-run plus handcrafted sample artifact.
2. Async structural-change paths stop calling sync `AsyncFileTools` bridges, and the bridge fails closed when invoked from a running event loop.
3. `log_event()` stops treating severity as inert payload data and routes records through the configured logger while preserving current JSON log artifacts.
4. The organization loop yields even when card execution returns quickly.
5. The review-run PR path fetches one PR snapshot per invocation.
6. `halt_session` returns `404` for unknown sessions.
7. Settings/preferences imports no longer mutate the filesystem, and legacy preference migration stops rerunning unconditionally on each cold start.
8. Driver strict parsing, conversation failure signaling, and structural-change response text each tell the truth about runtime behavior.
9. Targeted verification passes, or any remaining blocker is stated concretely.

## Execution Order

1. `OBT-1` false-green nightly quant gate truth
2. `OBT-2` async executor boundary safety
3. `OBT-3` logging truth and severity routing
4. `OBT-4` organization-loop fairness
5. `OBT-5` review-run PR single-load path
6. `OBT-6` session halt truth
7. `OBT-7` settings/preferences import and migration truth
8. `OBT-8` driver truth-surface cleanup
9. verification and closeout decision

## Work Items

### OBT-1: Reclassify Quant Sweep Nightly As Structural Proof Or Wire To Real Output

Problem:
1. The workflow currently runs `--dry-run`, synthesizes perfect KPI JSON, and then presents those values as an enforcement gate.

Implementation:
1. Remove the handcrafted KPI artifact path from the nightly workflow.
2. Either:
   1. wire the report/check steps to real sweep output, or
   2. keep the job as a structural dry-run and rename the steps/artifacts so they no longer claim runtime KPI enforcement.
3. Add a workflow contract test that enforces the truthful dry-run or real-output shape.

Acceptance:
1. No nightly step claims KPI enforcement unless it consumes real sweep output.
2. Automated tests pin the truthful wording and artifact path.

Proof target:
1. contract test

### OBT-2: Fail Closed On Sync-Async Bridge Use From Running Loops

Problem:
1. The current bridge can block a running event loop, and the active driver structural-change path still uses sync file helpers from async code.

Implementation:
1. Convert the async structural-change path to await `AsyncFileTools` methods directly.
2. Change `run_coroutine_blocking()` to reject use from a running event loop with a stable error.
3. Add tests that prove:
   1. async structural changes do not use the sync bridge
   2. the bridge errors instead of blocking when called from an active loop

Acceptance:
1. The validated async path is async-safe.
2. The shared bridge no longer advertises a safe behavior it cannot provide on an event-loop thread.

Proof target:
1. contract test
2. integration test

### OBT-3: Make Unified Logging Truthful About Severity And Logger Wiring

Problem:
1. `log_event()` blocks on direct file writes, bypasses `_logger`, and drops legacy severity into the JSON payload blob.

Implementation:
1. Centralize per-workspace log-path setup so it is not re-created on every write.
2. Route each event through `_logger` at the resolved severity while preserving the current JSON log artifact output.
3. Preserve subscriber notifications and runtime-event artifacts without silently dropping severity.
4. Add tests for:
   1. stdlib logger delivery
   2. legacy level routing
   3. JSON log artifact preservation

Acceptance:
1. `_logger` receives records.
2. Legacy severity affects routing instead of living only inside the payload blob.
3. The current artifact contract remains readable and deterministic.

Proof target:
1. contract test
2. integration test

### OBT-4: Guarantee A Yield In Organization Loop Hot Path

Problem:
1. The loop can rescan immediately after a fast card execution and monopolize the event loop with repeated synchronous organization scans.

Implementation:
1. Move `_find_next_critical_card()` off the event loop with `asyncio.to_thread(...)`.
2. Add a guaranteed yield after each iteration.
3. Add a targeted async test for fast-card execution fairness.

Acceptance:
1. A fast `run_card()` completion does not cause a tight rescan spin on the event loop thread.

Proof target:
1. integration test

### OBT-5: Collapse PR Review Loading To One Snapshot Fetch

Problem:
1. `run_pr()` currently fetches the full PR snapshot and then fetches it again for filtered code paths.

Implementation:
1. Reuse the first fetched snapshot and filter the changed files/diff in-process.
2. Add a service-level test that proves `load_from_pr()` is called once in `code_only` mode.

Acceptance:
1. One `run_pr()` call performs one PR snapshot fetch.

Proof target:
1. contract test

### OBT-6: Return 404 For Unknown Session Halt Requests

Problem:
1. The halt endpoint currently reports success for typoed or unknown session ids.

Implementation:
1. Check `engine.run_ledger.get_run(session_id)` before calling `halt_session`.
2. Raise `HTTPException(status_code=404, ...)` when no session exists.
3. Add an API test for the missing-session path.

Acceptance:
1. Unknown sessions do not return `ok: true`.

Proof target:
1. integration test

### OBT-7: Remove Settings Import Side Effects And Repeated Migration Work

Problem:
1. Importing settings creates config directories immediately, and preference migration reruns on each cold start.

Implementation:
1. Defer config-directory creation until actual settings/preferences reads or writes that need it.
2. Add a persistent migration marker so legacy preference migration is not rerun unconditionally on each cold start.
3. Add tests for:
   1. import/path resolution without filesystem mutation
   2. one-time migration marker behavior

Acceptance:
1. Importing settings alone does not create config directories.
2. Legacy preference migration does not rewrite both files on every cold start.

Proof target:
1. contract test

### OBT-8: Tighten Driver Truth Surface

Problem:
1. Strict parsing overstates validation, conversation failures disappear without signal, and structural failures receive success-flavored narration.

Implementation:
1. Replace brace-position theater with direct strict JSON parsing and a clear parse failure.
2. Log conversational provider failures before returning the generic conversation fallback.
3. Append `Strategic Insight` only on successful structural mutations.
4. Remove the dead `_load_engine_configs()` `hasattr` guards.
5. Add or update driver tests for each touched behavior.

Acceptance:
1. Strict parsing truthfully reflects real JSON validation.
2. Swallowed conversational model failures become observable.
3. Structural error text no longer implies success.
4. Dead defensive guards are removed from the touched path.

Proof target:
1. unit test
2. contract test

## Verification Plan

Targeted commands:
1. `python -m pytest tests/core/test_runtime_event_logging.py tests/runtime/test_logging_isolation.py tests/platform/test_nightly_workflow_memory_gates.py tests/platform/test_quality_workflow_gates.py tests/application/test_driver_action_parity.py tests/application/test_driver_config_loading.py tests/application/test_driver_conversation.py tests/application/test_driver_json_parse_modes.py tests/application/test_review_run_service.py tests/application/test_settings_preferences_migration.py tests/interfaces/test_api.py tests/platform/test_hardware_metrics_cache.py -q`
2. `python scripts/governance/check_docs_project_hygiene.py`

Additional targeted files may be added if the cycle introduces new tests for the async bridge, organization loop, or quant nightly workflow contract.

## Stop Conditions

1. Stop when all scoped work items above are complete and verified.
2. Stop early if the change set would exceed 10,000 changed lines.
3. If live integration proof would require unavailable external infrastructure, fix the truth-surface claim instead of over-claiming runtime KPI verification.

## Working Status

1. `OBT-1` completed
2. `OBT-2` completed
3. `OBT-3` completed
4. `OBT-4` completed
5. `OBT-5` completed
6. `OBT-6` completed
7. `OBT-7` completed
8. `OBT-8` completed
9. verification completed

## Verification Summary

1. targeted pytest gate: `python -m pytest tests/application/test_async_executor_service.py tests/application/test_organization_loop.py tests/core/test_runtime_event_logging.py tests/runtime/test_logging_isolation.py tests/platform/test_quant_sweep_nightly_workflow.py tests/platform/test_nightly_workflow_memory_gates.py tests/platform/test_quality_workflow_gates.py tests/application/test_driver_action_parity.py tests/application/test_driver_config_loading.py tests/application/test_driver_conversation.py tests/application/test_driver_json_parse_modes.py tests/application/test_review_run_service.py tests/application/test_settings_preferences_migration.py tests/interfaces/test_api.py -q` -> `149 passed`
2. docs hygiene gate passed after archive handoff: `python scripts/governance/check_docs_project_hygiene.py`

## Closeout Status

1. Completed on 2026-03-08.
2. Archived on 2026-03-08 under `docs/projects/archive/techdebt/OBT03082026/`.
3. The cycle converted the nightly quant sweep from a false KPI gate into a truthful dry-run artifact lane, removed unsafe async bridge use from the validated structural-change path, routed unified logging through the configured stdlib logger with first-class severity, guaranteed hot-path yields in the organization loop, collapsed PR review loading to one snapshot fetch, returned `404` for missing halt-session calls, removed settings import side effects and repeated preference migration work, and tightened the remaining driver truth surfaces.
