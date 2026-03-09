# Companion UI Remaining Work Register

Last updated: 2026-03-09
Status: Closed (MVP remaining work complete)
Owner: Orket Core
Parent authority: `docs/projects/Companion/11-COMPANION-CANONICAL-IMPLEMENTATION-PLAN.md`
UI contract authority: `docs/specs/COMPANION_UI_MVP_CONTRACT.md`

## 1. Purpose

This file tracked all remaining Companion MVP/UI closeout work.

Closeout outcome:
1. All previously open P0/P1/P2 closeout items in this register are complete.
2. Companion MVP is closed with strict auth mode support, gateway hardening, UI behavioral tests, and live integration evidence.
3. Post-MVP deferred work remains explicitly deferred.

## 2. Closed Items

### 2.1 Live end-to-end proof for UI stack and host seam

Status: Completed

Evidence:
1. `docs/projects/Companion/13-UI-LIVE-INTEGRATION-EVIDENCE-2026-03-09.md`

Observed summary:
1. Host + gateway cross-process flow verified live.
2. Chat/config/voice controls succeeded through gateway.
3. STT-unavailable degradation was explicitly observed and recorded as degraded (not failed).
4. Strict-key mode and cross-origin mutation blocking were both verified live.

### 2.2 Strict companion key-policy mode

Status: Completed

Delivered:
1. `ORKET_COMPANION_KEY_STRICT` policy toggle implemented in `orket/interfaces/api.py`.
2. Strict mode rejects `ORKET_API_KEY` on Companion routes when `ORKET_COMPANION_API_KEY` is configured.
3. Compatibility mode remains explicit default.
4. Integration coverage added in `tests/interfaces/test_companion_api_alias_routes.py`.

### 2.3 Extension gateway browser-surface hardening

Status: Completed

Delivered:
1. Loopback enforcement (`COMPANION_GATEWAY_REQUIRE_LOOPBACK`, default `true`).
2. Same-origin mutating-route guard (`COMPANION_GATEWAY_REQUIRE_SAME_ORIGIN`, default `true`).
3. Explicit config/chat/audio payload size guards with stable `413` error codes.
4. Gateway hardening test coverage in `tests/application/test_external_extension_template_server.py`.

### 2.4 UI-level automated behavioral tests

Status: Completed

Delivered:
1. Frontend browser-like behavioral tests (Vitest + jsdom + Testing Library) in:
   - `docs/templates/external_extension/src/companion_app/frontend/src/App.test.tsx`
2. Covered behaviors:
   - explicit text submission remains explicit after voice control changes
   - voice control visibility and state command wiring
   - pane swap behavior
   - avatar asset failure fallback rendering
   - keyboard traversal from rail to chat composer

### 2.5 Host/extension auth observability

Status: Completed

Delivered:
1. Structured auth rejection event (`api_auth_rejected`) with route class and reason.
2. Scoped-key misuse on core routes emits explicit rejection reason.
3. Security posture logs now include strict-mode state.
4. No credential material is logged.

### 2.6 Companion key rotation runbook

Status: Completed

Delivered:
1. Rotation/cutover/rollback procedure added to `docs/RUNBOOK.md` under `Companion Key Rotation`.
2. Includes host-first then gateway cutover order and smoke checks.

### 2.7 Accessibility and resilience pass

Status: Completed for MVP scope

Delivered:
1. Focus-visible ring styling (teal deep) across inputs/buttons/switch/accordion triggers.
2. Keyboard traversal automation added in frontend behavior tests.
3. Asset-failure fallback behavior retained and tested.

## 3. Post-MVP Deferred Queue (Unchanged)

These remain intentionally deferred unless explicitly reprioritized:
1. Production avatar system and richer expression rigging.
2. Lip-sync upgrade from amplitude baseline to viseme timeline.
3. Full real-time media path (WebRTC audio) for low-latency speech.
4. Premium motion design and final art polish.
5. Expanded emotion engine semantics.

Guardrail:
1. Deferred work must preserve host authority boundary and locked MVP contracts.
