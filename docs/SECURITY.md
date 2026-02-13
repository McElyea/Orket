# Orket Security and Governance

This document defines security requirements for API/webhook boundaries, configuration posture, and release canary checks.

## 1. API Auth Policy (`/v1/*`)
1. `/v1/*` endpoints are protected by `X-API-Key`.
2. Default behavior is fail-closed:
   - if `ORKET_API_KEY` is unset, requests are rejected.
3. Insecure local bypass is explicit and opt-in only:
   - `ORKET_ALLOW_INSECURE_NO_API_KEY=true`
4. Startup logs emit security posture and warn when insecure bypass is enabled.

## 2. Webhook Trust Boundary (`/webhook/*`)
1. `/webhook/gitea` requires:
   - `X-Gitea-Signature` header present
   - valid HMAC signature against `GITEA_WEBHOOK_SECRET`
2. Unsigned and invalidly signed requests are rejected before handler logic.
3. `/webhook/test` is disabled by default and requires:
   - `ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT=true`
   - plus auth:
     - `ORKET_WEBHOOK_TEST_TOKEN` via `X-Webhook-Test-Token`, or
     - `ORKET_API_KEY` via `X-API-Key`
4. If test endpoint is enabled without auth secret, startup logs emit warning.

## 3. Environment Matrix
### Local Dev
1. `ORKET_API_KEY` set (recommended), or explicit insecure bypass for temporary local debug.
2. `ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT` normally `false`.
3. If enabling `/webhook/test`, set `ORKET_WEBHOOK_TEST_TOKEN`.

### CI
1. Use strict auth posture (no insecure bypass).
2. Run tests and release canary checks.
3. Keep webhook test endpoint disabled unless a specific test requires it.

### Production
1. `ORKET_API_KEY` required.
2. `ORKET_ALLOW_INSECURE_NO_API_KEY` must be unset/false.
3. `GITEA_WEBHOOK_SECRET` required.
4. `ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT` must be unset/false.

## 4. Filesystem Boundary
1. Runtime file operations stay inside approved workspace boundaries.
2. Path traversal outside approved roots is denied.
3. Write operations are limited to authorized output locations.

## 5. State and Governance Boundary
1. State transitions must pass state machine rules.
2. Tool calls must pass tool-gate validation before execution.
3. Governance violations block progression.

## 6. Auditability and Canary Checks
1. Session/runtime actions are observable through logs and datastore records.
2. `scripts/security_canary.py` validates:
   - fail-closed API auth
   - mandatory webhook signature
   - disabled webhook test endpoint by default
3. `scripts/release_smoke.py` runs security canary by default.
