# Orket TechDebt Implementation Plan (Review3)

Date: 2026-03-02  
Source: `docs/projects/techdebt/Review3.md`

## Progress Snapshot

As of 2026-03-02 (America/Denver):

1. C1 complete: unified `ModelTimeoutError` to canonical `orket.exceptions.ModelTimeoutError`.
2. C2 in progress: `/v1/system/metrics` no longer performs direct blocking call in async endpoint (uses `asyncio.to_thread`).
3. C5 complete (initial hardening): Gitea artifact git remote URL no longer embeds credentials; auth passed via transient git config env header.
4. C6 complete: removed `lru_cache` from sync-async bridge method in config loader.
5. M9 complete: deduplicated API method resolver logic into shared helper.
6. H1 complete: made filesystem path-lock creation atomic with class-level guard lock.
7. H4 complete: Gitea vendor now validates `epic_id` as a positive integer label id before outbound issue queries/creates.
8. H7 complete: sandbox `service` parameter now validated against explicit allowlist before docker-compose logs invocation.

Verification executed:

1. `python -m pytest tests/application/test_turn_executor_timeout_error.py tests/adapters/test_gitea_artifact_exporter.py tests/platform/test_config_loader.py tests/interfaces/test_api.py -k "gitea or timeout or metrics or unsupported_runtime_method or config_loader" -q`
2. `python -m pytest tests/application/test_turn_executor_middleware.py tests/application/test_turn_executor_context.py tests/application/test_turn_executor_token_states.py tests/application/test_turn_executor_replay.py tests/application/test_turn_executor_skill_contract.py tests/application/test_memory_trace_emission.py -q`
3. `python -m pytest tests/interfaces/test_api.py tests/platform/test_hardware_metrics_cache.py tests/application/test_execution_pipeline_run_ledger.py -q`
4. `python -m pytest tests/adapters/test_sandbox_command_runner.py tests/adapters/test_sandbox_compose_generation.py tests/adapters/test_parallel_file_locking.py tests/integration/test_toolbox_refactor.py tests/adapters/test_gitea_vendor.py tests/adapters/test_gitea_webhook.py tests/interfaces/test_webhook_factory.py tests/interfaces/test_webhook_rate_limit.py -q`

## Objective

Execute Review3 remediation in risk order: stop deployment blockers first, then structural refactors, then medium-debt cleanup.

## Scope

In scope:
1. All `C*`, `H*`, and selected `M*` findings from Review3.
2. Security, async/runtime safety, and contract consistency.
3. Test and CI hardening for these changes.

Out of scope (this cycle):
1. Low-priority cosmetic improvements (`L*`) unless touched by required fixes.
2. Broad architecture redesign not required by Review3 findings.

## Success Criteria

1. All critical findings C1-C6 are closed.
2. `tests` suite is green (including currently failing tests cited in Review3).
3. No blocking `subprocess.run()` remains in async request/runtime hot paths.
4. API security posture meets:
   1. no insecure bypass in production profile
   2. query-token websocket auth denied in enforce mode
5. Enforcement gate artifacts report green:
   1. `benchmarks/results/security_compat_warnings.json`
   2. `benchmarks/results/security_compat_expiry_check.json`
   3. `benchmarks/results/security_enforcement_flip_gate.json`

## Workstreams

### WS-1: Deployment Blockers (C1-C6)

#### C1 Duplicate `ModelTimeoutError`
1. Remove duplicate in `orket/application/workflows/turn_executor.py`.
2. Import canonical class from `orket/exceptions.py`.
3. Add/adjust tests for timeout handling path.

#### C2 Blocking subprocess in async paths
1. Inventory and classify all 20 call sites.
2. Replace in async/runtime paths with:
   1. `asyncio.create_subprocess_exec()` where async process output is required
   2. `await asyncio.to_thread(subprocess.run, ...)` where minimal wrapper is acceptable
3. Add regression tests for non-blocking behavior in key paths.

#### C3 Blocking file I/O in async paths
1. Prioritize Review3 hotspots:
   1. `orket/application/services/memory_commit_buffer.py`
   2. `orket/application/workflows/turn_artifact_writer.py`
   3. `orket/domain/reconciler.py`
   4. `orket/runtime/config_loader.py`
2. Migrate reads/writes to async-safe wrappers (`AsyncFileTools` or `to_thread`).
3. Add targeted tests to verify behavior parity and deterministic outputs.

#### C4 `api.py` god file split
1. Extract routers incrementally with no API contract drift:
   1. `routers/system.py`
   2. `routers/cards.py`
   3. `routers/sessions.py`
   4. `routers/kernel.py`
   5. `routers/settings.py`
   6. `routers/streaming.py`
2. Keep endpoint paths and payload contracts stable.
3. Add parity tests for selected endpoints after each extraction.

#### C5 Credential exposure in Git push URLs
1. Remove URL construction that embeds password.
2. Switch to credential helper or token/header/SSH mechanism without secrets in URL strings.
3. Add tests/assertions to prevent reintroduction.

#### C6 `lru_cache` sync-async bridge issue
1. Remove bridge-layer cache in `orket/runtime/config_loader.py`.
2. If needed, add async-layer cache with explicit invalidation.
3. Add tests for stale-config avoidance.

### WS-2: High-Risk Structural/Security (H1-H7)

#### H1 Path lock race
1. Make lock creation atomic in `orket/adapters/tools/families/filesystem.py`.
2. Add concurrency test for same-path lock contention.

#### H2 `OrchestrationEngine` decomposition
1. Extract least-coupled capabilities first:
   1. archival
   2. sandbox ops
   3. kernel passthrough
2. Keep facade compatibility to avoid broad callers breakage.

#### H3 Verification runner isolation
1. Introduce containerized execution mode for verification fixtures.
2. Disable unsafe direct module execution in production profile.
3. Keep local-dev fallback only behind explicit dev flag.

#### H4 SSRF guard in Gitea vendor
1. Validate `epic_id` as allowed/known value before outbound request.
2. Add strict input validation tests.

#### H5 Duplicate transition definitions
1. Make `core/domain/state_machine.py` canonical.
2. Remove duplicate hardcoded matrices from other files and import canonical policy.
3. Ensure previously failing dependency/policy tests are green.

#### H6 Proxy magic reduction
1. Replace high-risk `__getattr__` proxy patterns with explicit forwarding where practical.
2. Prioritize security-sensitive/runtime-critical proxies.

#### H7 Sandbox service parameter validation
1. Add strict service allowlist validation in sandbox logs path.
2. Add tests for invalid service rejection.

### WS-3: Medium Debt (Selected M-items)

1. M1 compatibility shim reduction (remove unused re-export shims).
2. M3 `extra='forbid'` migration for Pydantic models in critical config/domain models.
3. M6 critical-path calculator naming/logic correction plus tests.
4. M9 duplicate API method resolver dedupe.
5. M10 short-id collision risk mitigation (replace truncated UUID).

## Execution Order

1. Phase A (Week 1): C1, C2 (top 5 hot paths), C5, C6, failing-test fixes.
2. Phase B (Week 2): C3 hotspot migrations, H1, H7, H4.
3. Phase C (Week 3): C4 router split (with parity tests), H5.
4. Phase D (Week 4+): H2, H3, H6, selected M-items.

## Test and Validation Plan

1. Run targeted tests per slice first.
2. Run full required lanes before merge:
   1. `python -m pytest tests/core tests/application tests/adapters tests/interfaces tests/platform -q`
   2. `python -m pytest tests/integration tests/runtime tests/contracts -q`
   3. `python -m pytest tests/acceptance tests/kernel/v1/test_odr_refinement_behavior.py -q`
3. Security artifacts/gates:
   1. `python scripts/run_security_regression_suite.py`
   2. `python scripts/export_security_compat_warnings.py`
   3. `python scripts/check_compat_fallback_expiry.py`
   4. `python scripts/check_security_enforcement_flip_gate.py`

## Deliverables

1. Code fixes for all C1-C6 findings.
2. Updated tests covering touched risk areas.
3. Router split PR-sized slices with parity evidence.
4. Updated `docs/projects/techdebt/README.md` with progress and closure status.
5. Enforcement/security artifacts committed when changed.

## Risks and Mitigations

1. Risk: large `api.py` split causes endpoint drift.
   1. Mitigation: router-by-router extraction with contract tests.
2. Risk: async migration introduces behavioral regressions.
   1. Mitigation: migrate by hotspot with deterministic regression tests.
3. Risk: verification isolation blocks existing local workflows.
   1. Mitigation: explicit dev-mode fallback and documented toggle.
