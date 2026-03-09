# Companion UI Remaining Work Register

Last updated: 2026-03-09
Status: Active
Owner: Orket Core
Parent authority: `docs/projects/Companion/11-COMPANION-CANONICAL-IMPLEMENTATION-PLAN.md`
UI contract authority: `docs/specs/COMPANION_UI_MVP_CONTRACT.md`

## 1. Purpose

This document consolidates all currently remaining Companion UI work into one execution register.

Use this for:
1. MVP closeout sequencing
2. security hardening follow-through
3. truthful verification closure
4. post-MVP queue shaping

This document does not replace the canonical lane pointer in roadmap; it is an execution companion to `11-COMPANION-CANONICAL-IMPLEMENTATION-PLAN.md`.

## 2. Remaining Work (P0: MVP-Close and Security-Critical)

### 2.1 Live end-to-end proof for current UI stack and host seam

Why still open:
1. Local tests and cross-process probes pass, but complete browser + extension gateway + host runtime evidence is not yet captured as durable lane evidence.

Required work:
1. Run host API with key auth enabled.
2. Run extension gateway with required `COMPANION_API_KEY`.
3. Exercise full UI flows from browser:
   - chat send/receive
   - mode/style update + next-turn effect
   - memory toggle update + session clear
   - voice controls (`start/submit/stop`) with explicit text-submit unaffected
   - STT unavailable degraded state visibility
4. Record observed paths (`primary`, `degraded`, `blocked`) and observed results (`success`, `failure`, `partial success`, `environment blocker`).

Definition of done:
1. Durable evidence artifact committed under Companion lane docs or benchmarks path with timestamped run summary.
2. No over-claiming: each unverified path explicitly called out.

Suggested command baseline:
1. `python server.py --port 8082`
2. `python -m uvicorn companion_app.server:app --app-dir src --host 127.0.0.1 --port 3000`
3. Browser run against `http://127.0.0.1:3000` with host/gateway keys set.

### 2.2 Strict companion key-policy mode (no fallback to core key on companion routes)

Current behavior:
1. `ORKET_COMPANION_API_KEY` is supported and scoped.
2. `ORKET_API_KEY` is still accepted on companion routes for operator/admin compatibility.

Why still open:
1. This is secure but not strict least-privilege by default.

Required work:
1. Add a host policy switch for strict mode (for example `ORKET_COMPANION_KEY_STRICT=true`).
2. In strict mode, reject `ORKET_API_KEY` on companion routes when `ORKET_COMPANION_API_KEY` is configured.
3. Add tests for strict and compatibility modes.
4. Update docs and `.env.example` with exact semantics.

Definition of done:
1. Companion-only key can be enforced without ambiguity.
2. Test coverage proves non-companion route isolation and strict-mode behavior.

### 2.3 Extension gateway browser-surface hardening

Current behavior:
1. Gateway now fails closed when `COMPANION_API_KEY` is missing.

Why still open:
1. Browser-to-gateway trust boundary is still minimal (no CSRF/session binding controls yet).

Required work:
1. Add CSRF/session-origin guard for mutating gateway routes.
2. Enforce local-loopback default binding and document remote exposure risk.
3. Add explicit request-size/time limits for audio and chat payloads.

Definition of done:
1. Browser cannot invoke privileged mutating routes from cross-site contexts without explicit opt-in.
2. Security behavior is tested and documented.

## 3. Remaining Work (P1: MVP Confidence and Operability)

### 3.1 UI-level automated behavioral tests

Why still open:
1. Contract/integration tests cover server/gateway seams, but browser interaction assertions are still mostly manual.

Required work:
1. Add browser-level tests (Playwright or equivalent) for:
   - explicit text submission behavior
   - voice control panel visibility and state updates
   - pane swap behavior
   - graceful fallback when optional avatar asset fails
2. Keep tests deterministic and host-seam focused (no runtime authority duplication).

Definition of done:
1. Deterministic browser tests run locally and in CI template lane.

### 3.2 Host/extension auth observability

Why still open:
1. We log security posture, but auth failure analytics and route-scope telemetry are limited.

Required work:
1. Add structured auth failure counters by route class (`companion`, `core`).
2. Add explicit event for scoped-key rejection on non-companion endpoints.
3. Ensure logs never include raw credential material.

Definition of done:
1. Operators can distinguish misconfiguration vs attack/noise quickly.

### 3.3 Key rotation runbook for Companion integration

Why still open:
1. Key model exists, but operational rotation and rollback procedure is not codified for Companion.

Required work:
1. Write a short runbook section for rotating `ORKET_API_KEY` and `ORKET_COMPANION_API_KEY` safely.
2. Include cutover order (host first/extension second), rollback, and smoke checks.

Definition of done:
1. Rotation can be done without service ambiguity.

## 4. Remaining Work (P2: Product-Quality Closeout)

### 4.1 Finalize MVP closeout handshake for Companion lane phase

Why still open:
1. Lane is active and in progress; closeout packaging not yet complete.

Required work:
1. Update roadmap/lane status when MVP close criteria are met.
2. Archive phase-scoped docs only when complete, keeping initiative-level plan active if later phases remain.
3. Ensure Companion active folder contains current initiative authority and canonical current plan.

Definition of done:
1. Roadmap reflects truthful status and no stale active docs remain.

### 4.2 Accessibility and resilience pass

Why still open:
1. Core UI behavior exists, but accessibility and resilience pass is not yet formally completed.

Required work:
1. Keyboard-only traversal audit for rail/chat/accordion controls.
2. Focus visibility audit (teal deep ring) across all inputs and toggles.
3. Asset failure and slow-host loading state polish.

Definition of done:
1. Companion remains usable and legible under keyboard-only and degraded asset/network conditions.

## 5. Remaining Work (Post-MVP Deferred Queue)

These remain intentionally deferred unless reprioritized:
1. Production avatar system and richer expression rigging.
2. Lip-sync upgrade from amplitude baseline to true viseme timeline.
3. Full real-time media path (WebRTC audio) if low-latency speech becomes required.
4. Premium motion design and final art polish.
5. Expanded emotion engine semantics.

Guardrail:
1. Deferred work must preserve host authority boundary and locked MVP contracts.

## 6. Suggested Execution Order

1. P0.1 live end-to-end evidence capture.
2. P0.2 strict companion-key mode implementation.
3. P0.3 gateway browser-surface hardening.
4. P1.1 browser-level automated tests.
5. P1.2/P1.3 auth observability + rotation runbook.
6. P2 closeout and accessibility pass.

## 7. Verification Checklist Template

Use this checklist on each remaining slice:
1. Layer label declared (`unit`, `contract`, `integration`, `end-to-end`).
2. Real runtime path exercised when integration behavior changed.
3. Observed path recorded (`primary`, `degraded`, `blocked`).
4. Observed result recorded (`success`, `failure`, `partial success`, `environment blocker`).
5. Exact failing step/error captured when blocked.
6. Docs and authority sources updated in same change when behavior/policy changed.
