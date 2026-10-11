# Orket Security and Governance

This document defines security requirements for API/webhook boundaries, configuration posture, and security verification.

Last reviewed: 2026-10-10. Application authority:
`orket/application/services/api_authentication_service.py` and
`orket/runtime/config/startup_checks.py`.

## 1. API Auth Policy (`/v1/*`)
1. `/v1/*` endpoints are protected by `X-API-Key`.
2. Generic extension runtime routes under `/v1/extensions/{extension_id}/runtime/*` use the same core API key posture as the rest of `/v1/*`.
3. Orket core does not admit Companion-scoped API keys or Companion-only host routes.
4. Default behavior is fail-closed:
   - if `ORKET_API_KEY` is unset, requests are rejected.
5. API key comparison uses timing-safe comparison for supplied `X-API-Key` values.
6. Insecure local bypass is explicit and opt-in only:
   - `ORKET_ALLOW_INSECURE_NO_API_KEY=true`, a non-production
     `ORKET_API_SECURITY_PROFILE` (for example `dev`), and a local `ORKET_ENV`.
   - The default security profile is `production`, which still rejects anonymous
     requests. A configured key still has to match even when bypass is enabled.
   - `ORKET_ENV=production` or `staging` refuses bypass at startup.
7. Startup refuses non-local environments when required secrets are missing or still set to documented placeholders:
   - `ORKET_ENCRYPTION_KEY`
   - `SESSION_SECRET`
   - `GITEA_WEBHOOK_SECRET`
   - `ORKET_API_KEY`
8. Startup logs emit security posture and warn when insecure bypass is enabled.
9. Auth rejection telemetry (`api_auth_rejected`) is emitted without credential material.
10. Companion gateway/BFF auth is external to Orket core:
   - the gateway sends the host credential through `COMPANION_API_KEY` or `ORKET_API_KEY`
   - the gateway continues to enforce its own loopback and same-origin protections on `/api/*`

`GET /health` is deliberately unauthenticated and returns only liveness. The
WebSocket routes use the same captured host authentication inputs: headers are
supported in every mode; query-string keys are compatibility-only and are rejected
by `ORKET_API_SECURITY_MODE=enforce`. Do not put credentials in shared URLs/logs.
Changing shell settings does not reconfigure an already constructed API owner;
restart the host to change its captured authentication inputs.

Governed-agent delivery at `/v1/agent-webhooks/{issuer_ref}/deliveries/{delivery_id}`
requires both the core API key and its configured issuer HMAC/timestamp headers.
It is separate from the standalone Gitea webhook service described below.

## 1.1. Browser CORS Policy
1. Browser CORS is denied by default with `allow_origins=[]`.
2. Operators must set `ORKET_ALLOWED_ORIGINS` to a comma-separated explicit allowlist before browser clients can call the host API cross-origin.
3. CORS credentials remain disabled by default.

## 1.2. Kernel Outbound Projection Policy
1. Kernel projection packs apply `orket/kernel/v1/outbound_policy_gate.py` before digesting or returning projected policy/tool context.
2. The gate redacts configured field paths, sensitive key leaves, email-like values, built-in leak patterns, and configured forbidden regex patterns.
3. The projection response reports redaction counts and field paths under `policy_summary.outbound_policy_gate` without exposing the original values.
4. Outward API surfaces use the same gate before operator-visible serialization.
5. Gate configuration can be supplied with `ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS`, `ORKET_OUTBOUND_POLICY_FORBIDDEN_PATTERNS`, `ORKET_OUTBOUND_POLICY_ALLOWED_OUTPUT_FIELDS`, or a JSON file referenced by `ORKET_OUTBOUND_POLICY_CONFIG_PATH`.
6. Ledger exports that would require post-hash event-payload redaction are downgraded to partial verified views with hash-chain anchors instead of full canonical ledgers.

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
1. `ORKET_API_KEY` set (recommended), or the complete explicit local bypass posture above.
2. `ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT` normally `false`.
3. If enabling `/webhook/test`, set `ORKET_WEBHOOK_TEST_TOKEN`.
4. If running the external Companion gateway, set `COMPANION_API_KEY` or `ORKET_API_KEY` in that process environment.

### CI
1. Use strict auth posture (no insecure bypass).
2. Run the current API/webhook checks linked below alongside the applicable test selection.
3. Keep webhook test endpoint disabled unless a specific test requires it.

### Production
1. `ORKET_API_KEY` required and not a placeholder.
2. `ORKET_ENCRYPTION_KEY`, `SESSION_SECRET`, and `GITEA_WEBHOOK_SECRET` required and not placeholders.
3. `ORKET_ALLOW_INSECURE_NO_API_KEY` must be unset/false.
4. `ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT` must be unset/false.
5. `ORKET_ALLOWED_ORIGINS` must be explicit when a browser UI is deployed.

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
2. Use the current API authentication and webhook factory regression commands in
   [Testing Policy](TESTING_POLICY.md#cli-and-security-smoke). These exercise
   application lifetimes and admission; they are not live model proof.
3. The legacy `scripts/security/security_canary.py` still uses the removed module
   `app` singleton and currently fails before its assertions. The legacy
   `scripts/governance/release_smoke.py` depends on it. Neither is a passing
   security/release acceptance command until migrated to the application factories.
