# Orket Deep Critical Code Review

Date: 2026-02-24  
Mode: local review only (no push)

## Scope
- Architecture-level modularity blockers.
- Code-level runtime defects.
- Test and gate coverage gaps.
- Explicit focus: what remains to make Orket modular while keeping current contracts where possible.

## Findings (Priority Ordered)

### Critical 1: Logging is not workspace-isolated and leaks file handles
- Evidence:
  - `orket/logging.py:10-27` uses a global logger and adds a file handler per workspace.
  - `orket/logging.py:145-150` writes through the same global logger to all attached handlers.
- Impact:
  - Events for one workspace are written into other workspace logs (cross-run contamination).
  - Open file handles accumulate, making temp/ephemeral workspace cleanup unreliable on Windows.
  - This breaks a core modular requirement: module/workspace observability isolation.
- Repro:
  - Log one event to workspace A, then one to workspace B.
  - Workspace A log receives both events.

### Critical 2: `/v1/runs/{session_id}/metrics` can return `null` because metrics function never returns
- Evidence:
  - `orket/logging.py:198-232` builds `metrics` but does not `return metrics`.
  - `orket/interfaces/api.py:907-913` returns `metrics_reader(workspace)`.
- Impact:
  - API contract silently degrades to `null` for real runtime reader.
  - UI/automation depending on role metrics can fail or misreport.

### Critical 3: PR-open webhook path can crash at runtime due wrong type passed to `update_status`
- Evidence:
  - `orket/adapters/vcs/gitea_webhook_handler.py:116` passes `"code_review"` (string).
  - `orket/adapters/storage/async_card_repository.py:176-199` expects `CardStatus` and calls `status.value`.
- Impact:
  - Runtime `AttributeError` on PR open/synchronize review trigger path.
  - Webhook-based modular flow is unreliable at first state transition.

### Critical 4: Key architecture guard tests are effectively no-op due incorrect repo-root calculation
- Evidence:
  - `tests/platform/test_architecture_volatility_boundaries.py:7` uses `parents[1]` (resolves to `.../tests`).
  - `tests/platform/test_no_old_namespaces.py:5` same issue for first test.
  - `tests/platform/test_runtime_print_policy.py:10` same issue.
- Impact:
  - Multiple architecture guardrails pass while scanning wrong/nonexistent paths.
  - Dependency drift and policy regressions can land undetected.
  - This is a high-risk false-confidence defect in quality gates.

### High 5: Dependency-direction enforcement is incomplete and currently allows large ungoverned `root` surface
- Evidence:
  - `scripts/check_dependency_direction.py:17-28` maps many modules to `root`.
  - `scripts/check_dependency_direction.py:48-68` defines no restrictions for `root -> *`.
  - `docs/architecture/dependency_graph_snapshot.md:10` shows `root -> root` as dominant edge class.
- Impact:
  - A large part of the codebase is effectively outside hard boundary enforcement.
  - Modular decomposition cannot be validated by CI with current rules.

### High 6: Boundary policy mismatch between architecture doc and tests
- Evidence:
  - `docs/ARCHITECTURE.md:27-31` allows `application -> adapters`.
  - `tests/platform/test_architecture_volatility_boundaries.py:80-90` forbids `application -> adapters`.
- Impact:
  - Teams cannot know which rule is authoritative.
  - Refactors and module extraction decisions become inconsistent.

### High 7: Execution pipeline clears global default log after epic run
- Evidence:
  - `orket/runtime/execution_pipeline.py:523-525` truncates `workspace/default/orket.log`.
- Impact:
  - Shared observability history is removed unexpectedly.
  - Troubleshooting and auditability degrade across sessions.

### High 8: Interface modules instantiate heavyweight singletons at import time
- Evidence:
  - `orket/interfaces/api.py:37` creates runtime node at import.
  - `orket/interfaces/api.py:412` creates engine singleton at import.
  - `orket/webhook_server.py:33-45` creates webhook handler and enforces env at import.
- Impact:
  - Side effects on import reduce module composability and test isolation.
  - Optional install/module selection is difficult because imports trigger hard dependencies.

### Medium 9: Decision node registry is configurable but not truly pluggable for install-time module packs
- Evidence:
  - `orket/decision_nodes/registry.py:5-19` imports builtins statically.
  - `orket/decision_nodes/registry.py:43-72` pre-registers in-process defaults only.
- Impact:
  - Cannot cleanly attach/detach module packs via entrypoints/manifests at install/setup time.
  - Current model is "switch among bundled implementations", not "load optional module bundles".

### Medium 10: Monolithic hotspots remain concentrated in a few files
- Evidence:
  - `orket/application/workflows/turn_executor.py` ~2405 lines.
  - `orket/application/workflows/orchestrator.py` ~1857 lines.
  - `orket/interfaces/api.py` ~1787 lines.
- Impact:
  - High change-coupling and regression probability.
  - Harder to split by module/layer without high-risk edits.

### Medium 11: Setup dependency source-of-truth mismatch
- Evidence:
  - `README.md:51-54` instructs `pip install -r requirements.txt`.
  - `requirements.txt` is minimal vs broader runtime deps in `pyproject.toml:19-45`.
- Impact:
  - Fresh setup may miss runtime dependencies.
  - Undermines predictable module installation behavior.

### Medium 12: Tool gate file-type policy hook is likely dead path
- Evidence:
  - `orket/core/policies/tool_gate.py:98-100` checks `self.org.forbidden_file_types`.
  - `orket/schema.py:251-269` `OrganizationConfig` has `extra='ignore'` and no `forbidden_file_types`.
- Impact:
  - Intended policy may never activate from org config.
  - Governance behavior differs from operator expectations.

## Test and Gate Gaps

1. No test covers the real `get_member_metrics` return path.
- Existing API test stubs the metrics reader (`tests/interfaces/test_api.py:905-927`), so the production function defect is hidden.

2. No test covers PR `pull_request` opened/synchronized path with real status update call.
- Existing webhook tests focus on review-cycle paths (`tests/adapters/test_gitea_webhook.py:30-89`).

3. No test verifies logging isolation across multiple workspaces.
- Existing logging tests validate envelope/artifact shape only (`tests/core/test_runtime_event_logging.py:15-56`).

4. Architecture boundary tests must include a self-check that target scan roots exist and contain files.
- Current tests can pass with empty scans.

## What This Means For Modularity Right Now

Orket can move toward modularity, but not safely until these are fixed first:
1. Logging isolation and metrics correctness.
2. Webhook status type defect.
3. Broken architecture gate test roots.
4. Boundary rule source-of-truth alignment.

Without those fixes, modular decomposition work will build on unstable observability and weak enforcement.

## Contract-Safe vs Contract-Breaking Guidance

Contract-safe now:
1. Fix return/type/test-root defects.
2. Align architecture docs/tests/scripts to one boundary policy.
3. Introduce module registry/composition root without changing external API contracts.

Likely contract-breaking later (higher payoff, higher cost):
1. Strictly forbid direct `application -> adapters` imports and move to explicit ports everywhere.
2. Remove legacy `root` compatibility shims once all call sites migrate.

