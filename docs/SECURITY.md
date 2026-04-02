# Orket Security and Governance

This document defines security requirements for API/webhook boundaries, configuration posture, and release canary checks.

## 1. API Auth Policy (`/v1/*`)
1. `/v1/*` endpoints are protected by `X-API-Key`.
2. Generic extension runtime routes under `/v1/extensions/{extension_id}/runtime/*` use the same core API key posture as the rest of `/v1/*`.
3. Orket core does not admit Companion-scoped API keys or Companion-only host routes.
4. Default behavior is fail-closed:
   - if `ORKET_API_KEY` is unset, requests are rejected.
5. Insecure local bypass is explicit and opt-in only:
   - `ORKET_ALLOW_INSECURE_NO_API_KEY=true`
6. Startup logs emit security posture and warn when insecure bypass is enabled.
7. Auth rejection telemetry (`api_auth_rejected`) is emitted without credential material.
8. Companion gateway/BFF auth is external to Orket core:
   - the gateway sends the host credential through `COMPANION_API_KEY` or `ORKET_API_KEY`
   - the gateway continues to enforce its own loopback and same-origin protections on `/api/*`

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
4. If running the external Companion gateway, set `COMPANION_API_KEY` or `ORKET_API_KEY` in that process environment.

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
2. `scripts/security/security_canary.py` validates:
   - fail-closed API auth
   - mandatory webhook signature
   - disabled webhook test endpoint by default
3. `scripts/governance/release_smoke.py` runs security canary by default.
