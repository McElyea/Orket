# Orket Roadmap

Roadmap source of truth for active and upcoming remediation work.
Architecture authority: `docs/OrketArchitectureModel.md`.
Last updated: 2026-02-12.

## Security Policy
1. Security is fail-closed by default.
2. Public endpoint behavior must be test-backed with non-mocked integration coverage for critical paths.
3. Any endpoint in `/v1/*` or `/webhook/*` must have explicit auth policy, explicit error policy, and regression tests.
4. Green tests only counts when full intended suites are discoverable and import-clean.

## Priority Ladder
1. P0: Security containment (auth + webhook trust boundary).
2. P1: Runtime correctness (sandbox listing crash, task lifecycle leaks).
3. P2: Test integrity and CI signal restoration.
4. P3: Hardening and observability refinements.

## P0 Chunk Gate: Security Containment

### Objective
Close all externally reachable trust-boundary failures identified in review.

### Scope
1. API auth fail-closed behavior.
2. Mandatory webhook signature validation.
3. Removal or strict gating of test webhook endpoint in non-dev contexts.

### Work Items
1. API auth fail-closed by default.
- Change default policy in `orket/decision_nodes/builtins.py` so missing `ORKET_API_KEY` does not grant access.
- Add explicit opt-in local-dev bypass env flag (example: `ORKET_ALLOW_INSECURE_NO_API_KEY=true`) and keep it disabled by default.
- Ensure all `/v1/*` routes still use same dependency path in `orket/interfaces/api.py`.

2. Enforce signature presence for `/webhook/gitea`.
- Update `orket/webhook_server.py` to reject requests when `X-Gitea-Signature` is missing.
- Keep current HMAC validation path for present signatures.
- Return consistent auth error status/detail for missing vs invalid signatures.

3. Gate `/webhook/test` to safe contexts only.
- Preferred: disable in production by default and require explicit dev flag.
- Secondary: require API key or separate webhook test secret if endpoint remains available.
- Add startup warning log if unsafe mode is enabled.

4. Security regression tests.
- Add test: `/webhook/gitea` without signature returns auth failure.
- Add test: `/webhook/gitea` with invalid signature returns auth failure.
- Add test: `/webhook/test` blocked when dev flag disabled.
- Add test: `/v1/version` fails when `ORKET_API_KEY` missing and insecure bypass disabled.

### Acceptance Criteria
1. No unsigned request reaches webhook handler logic.
2. `/v1/*` is not publicly accessible when `ORKET_API_KEY` is unset unless explicit insecure override is enabled.
3. `/webhook/test` is not callable in default production configuration.
4. New security tests pass and fail if behavior regresses.

### Exit Evidence
1. Passing targeted tests in `tests/test_api.py`, `tests/test_webhook_rate_limit.py`, and any new webhook auth tests.
2. Manual sanity checks:
- Missing signature -> non-200.
- Invalid signature -> non-200.
- Missing API key in strict mode -> 403 on `/v1/version`.

## P1 Chunk Gate: Runtime Correctness and Reliability

### Objective
Eliminate confirmed runtime breakages and stale state tracking.

### Scope
1. Sandbox endpoint crash.
2. Active task lifecycle cleanup.

### Work Items
1. Fix `/v1/sandboxes` crash.
- Correct method mismatch in `orket/orchestration/engine.py` (`list_all` vs `list_active`).
- Verify behavior with real endpoint call path, not only monkeypatched tests.

2. Add run task lifecycle cleanup.
- In `orket/interfaces/api.py`, register task completion callback on scheduled tasks.
- Ensure callback removes task from `runtime_state` for success, failure, and cancellation.
- Protect callback path against race and missing-key cases.

3. Heartbeat task count correctness.
- Confirm `active_tasks` reflects in-flight tasks only.
- Add test with a short-lived async task and assert count eventually decrements.

### Acceptance Criteria
1. `GET /v1/sandboxes` returns 200 with valid JSON payload (or empty list), not 500.
2. `runtime_state.active_tasks` does not grow unbounded after completed runs.
3. Heartbeat task count converges to expected value after task completion.

### Exit Evidence
1. Endpoint regression tests added and passing.
2. Manual local call to `/v1/sandboxes` no longer throws `AttributeError`.

## P2 Chunk Gate: Test Integrity and CI Signal

### Objective
Ensure green CI actually represents repo health for intended test surfaces.

### Scope
1. Resolve broken `product/sneaky_price_watch/tests` package/import structure.
2. Decide and codify suite ownership and CI inclusion policy.

### Work Items
1. Triage and choose test strategy for `product/sneaky_price_watch`.
- Option A: Make tests importable by packaging/module path fixes.
- Option B: Mark as intentionally out-of-scope and move to `legacy/` or separate project.
- Option C: Keep separate but add explicit CI job and invocation contract.

2. Update pytest/CI discovery policy.
- Adjust `pyproject.toml` `testpaths` only if this suite is intended active.
- If excluded intentionally, document why and enforce via policy checks.

3. Add CI guardrails.
- Add a check ensuring intended test directories collect successfully.
- Fail CI on collection errors in included suites.

### Acceptance Criteria
1. Included test suites are import-clean during collection.
2. CI discovery configuration matches documented intent.
3. No silently broken in-repo suite remains in ambiguous state.

### Exit Evidence
1. `python -m pytest --collect-only -q` matches expected suite inventory.
2. CI job explicitly reports inclusion/exclusion rationale for product test subtree.

## P3 Chunk Gate: Hardening and Operational Follow-Through

### Objective
Reduce recurrence probability for this class of defects.

### Scope
1. Policy defaults and startup safety checks.
2. Threat-surface documentation.
3. Post-fix verification runbook.

### Work Items
1. Startup safety assertions.
- Emit startup warnings (or hard fail by mode) for unsafe auth/webhook config.
- Add explicit config summary in logs without leaking secrets.

2. Documentation alignment.
- Update `docs/SECURITY.md` with precise webhook and API auth requirements.
- Add explicit environment matrix: local-dev vs CI vs production.

3. Regression canary checks.
- Add lightweight smoke scripts for auth and webhook trust boundary validation.
- Integrate into release smoke process (`scripts/release_smoke.py` if appropriate).

### Acceptance Criteria
1. Security configuration requirements are unambiguous in docs.
2. Unsafe config states are visible immediately at startup.
3. Release smoke catches signature/auth regressions before deployment.

## Execution Sequence
1. Execute P0 fully before any non-security refactors.
2. Execute P1 immediately after P0 with strict endpoint verification.
3. Execute P2 next to restore confidence in test signal.
4. Execute P3 as hardening once correctness and security are stable.

## Milestone Tracking Template
Use this template when updating each chunk gate:

1. Completed:
- Itemized, file-specific changes.
- Tests added/updated.

2. Remaining:
- Explicit unfinished steps only.

3. Acceptance:
- Pass/fail on each criterion.

4. Evidence:
- Exact command outputs (pass/fail summary).

## Immediate Next Actions (First Implementation Batch)
1. Patch `is_api_key_valid` behavior to fail-closed and add opt-in insecure override.
2. Enforce required signature header for `/webhook/gitea`.
3. Gate `/webhook/test` behind explicit dev-only flag.
4. Add tests for all three.
5. Patch sandbox list method mismatch.
6. Add task completion cleanup callback and heartbeat-count regression test.

## Definition of Done for This Roadmap
1. All P0 and P1 acceptance criteria pass with automated tests.
2. P2 test-scope decision is finalized and encoded in CI config.
3. Security and runbook docs are updated to match runtime behavior.
4. No known critical/high findings from `Agents/CodexReview2.md` remain open.

## Execution Update (2026-02-12)

### P0 Status
Completed:
1. API auth default is now fail-closed in `orket/decision_nodes/builtins.py` (`is_api_key_valid`).
2. Added explicit insecure dev bypass toggle via `ORKET_ALLOW_INSECURE_NO_API_KEY`.
3. `/webhook/gitea` now requires `X-Gitea-Signature`; missing signatures are rejected in `orket/webhook_server.py`.
4. Invalid signatures continue to be rejected in `orket/webhook_server.py`.
5. `/webhook/test` is now disabled by default and gated by `ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT`.
6. Added regression coverage:
- strict `/v1/version` auth default and insecure bypass (`tests/test_api.py`)
- missing signature rejection (`tests/test_webhook_rate_limit.py`)
- invalid signature rejection (`tests/test_webhook_rate_limit.py`)
- test webhook endpoint disabled-by-default and enabled-by-flag behavior (`tests/test_webhook_rate_limit.py`)
7. Updated parity expectations for runtime auth policy in `tests/test_decision_nodes_planner.py`.

Remaining:
1. Optional hardening decision: require additional auth on `/webhook/test` even when enabled (currently dev-flag gated only).
2. Documentation updates in `docs/SECURITY.md` and env setup docs to include new flags.

Acceptance Check:
1. Unsigned webhook requests rejected: PASS.
2. `/v1/*` fail-closed when no API key and no bypass: PASS.
3. `/webhook/test` disabled by default: PASS.
4. Security regressions covered by tests: PASS.

### P1 Status
Completed:
1. Fixed `/v1/sandboxes` runtime crash by switching to `list_active()` in `orket/orchestration/engine.py`.
2. Added active task cleanup callback in `orket/interfaces/api.py` so completed/canceled tasks are removed from `runtime_state`.
3. Added regression tests:
- real `/v1/sandboxes` path no-crash assertion (`tests/test_api.py`)
- scheduled task cleanup lifecycle (`tests/test_api_task_lifecycle.py`)
- heartbeat active-task convergence via `/v1/system/heartbeat` after `run-active` completion (`tests/test_api_task_lifecycle.py`)

Remaining:
1. Stress test task cleanup under rapid concurrent run submissions.

Acceptance Check:
1. `/v1/sandboxes` no longer 500s from `list_all` mismatch: PASS.
2. Active task map cleanup after completion: PASS.
3. Heartbeat-specific convergence test: PASS.

### P2 Status
Completed:
1. Restored product suite executability by making `DataAccessor` backward-compatible with optional storage construction in `product/sneaky_price_watch/accessors/data_accessor.py`.
2. Added compatibility helper `get_page_data(...)` used by stealth browser flow/tests in `product/sneaky_price_watch/accessors/data_accessor.py`.
3. Added explicit CI job `product_quality` in `.gitea/workflows/quality.yml` to run:
- `pytest product/sneaky_price_watch/tests -q`
- with `PYTHONPATH=product/sneaky_price_watch`
4. Updated downstream workflow dependencies so smoke/migration gates require both `quality` and `product_quality`.
5. Validated product suite locally with CI-equivalent command.
6. Added Gitea publishing automation for `product/*` split repos via `scripts/publish_products_to_gitea.py`.
7. Documented product publish flow in `docs/RUNBOOK.md`.

Remaining:
1. Optional cleanup: migrate `product/sneaky_price_watch` imports from flat-module style to package-relative imports so `PYTHONPATH` override is no longer required.

Acceptance Check:
1. Included product suite is import-clean and passing in explicit CI command path: PASS.
2. CI discovery policy is now explicit (core + product jobs): PASS.
3. Product subtree is no longer silently broken/ignored: PASS.

### Verification Evidence
1. `python -m pytest tests/test_webhook_rate_limit.py -q` -> 5 passed.
2. `python -m pytest tests/test_api.py -q` -> 52 passed.
3. `python -m pytest tests/test_api_task_lifecycle.py -q` -> 2 passed.
4. `$env:PYTHONPATH='product/sneaky_price_watch'; python -m pytest product/sneaky_price_watch/tests -q` -> 17 passed.
5. `python -m pytest tests/ -q` -> 274 passed.
