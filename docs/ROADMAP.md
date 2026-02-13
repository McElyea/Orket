# Orket Roadmap

Roadmap source of truth for remediation and hardening work.
Architecture authority: `docs/OrketArchitectureModel.md`.
Last updated: 2026-02-13.

## Status
All tracked roadmap items are complete.  
No remaining open items in this roadmap.

## Completed Work Summary

### P0 Security Containment (Complete)
1. API auth is fail-closed by default (`/v1/*`).
2. Explicit insecure local bypass is opt-in (`ORKET_ALLOW_INSECURE_NO_API_KEY`).
3. `/webhook/gitea` requires signature header and valid HMAC.
4. `/webhook/test` is disabled by default and now requires auth when enabled:
   - `ORKET_WEBHOOK_TEST_TOKEN` via `X-Webhook-Test-Token`, or
   - `ORKET_API_KEY` via `X-API-Key`.
5. Startup security posture/warning logs added for API and webhook runtime.
6. Security regression tests updated and passing.

### P1 Runtime Correctness and Reliability (Complete)
1. `/v1/sandboxes` method mismatch fixed (`list_active`).
2. Active task cleanup callback implemented for run scheduling.
3. Heartbeat active-task convergence covered by tests.
4. Added concurrent stress test for task cleanup under rapid submissions.

### P2 Test Integrity and CI Signal (Complete)
1. CI policy for product suite is explicit and safe when suite directory is absent.
2. Workflow now handles retired/missing product test subtree without false failures.
3. Test policy guard added to minimize `unittest.mock` usage in unit tests.

### P3 Hardening and Operational Follow-Through (Complete)
1. `docs/SECURITY.md` updated with explicit auth/webhook requirements and env matrix.
2. Added security canary script: `scripts/security_canary.py`.
3. Integrated canary into release smoke: `scripts/release_smoke.py`.
4. Runbook/docs aligned for current operations and archive workflow.

## Verification Evidence
1. `python -m pytest tests/test_webhook_rate_limit.py -q` -> passed.
2. `python -m pytest tests/test_api_task_lifecycle.py -q` -> passed.
3. `python -m pytest tests/test_api.py -q` -> passed.
4. `python scripts/security_canary.py` -> SUCCESS.
5. `python -m pytest tests/ -q` -> `294 passed`.

## Definition of Done (Satisfied)
1. Security and runtime acceptance criteria pass with automated tests.
2. CI/test-scope intent is explicit.
3. Security and runbook docs reflect current runtime behavior.
4. No known critical/high findings from `Agents/CodexReview2.md` remain open.

## Next Trigger
Open a new roadmap only when a new externally visible risk, reliability regression, or scope expansion is accepted.
