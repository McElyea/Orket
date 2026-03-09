# Companion UI Live Integration Evidence

Last updated: 2026-03-09
Status: Completed
Owner: Orket Core
Related register: `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/12-UI-WORK-REMAINING.md`

## 1. Purpose

Capture durable live (non-mocked) Companion UI integration evidence for closeout.

This run validates:
1. host auth compatibility + strict-mode behavior
2. extension gateway to host connection
3. chat/config/voice control flows
4. explicit cross-origin mutation blocking
5. truthful degraded-path handling when STT is unavailable

## 2. Runtime Setup

Host:
1. Command: `python -m uvicorn orket.interfaces.api:app --host 127.0.0.1 --port 18082`
2. Env baseline:
   - `ORKET_API_KEY=core-key`
   - `ORKET_COMPANION_API_KEY=companion-key`
   - `ORKET_COMPANION_KEY_STRICT=false` (then `true` for strict pass)
   - `ORKET_ALLOW_INSECURE_NO_API_KEY=false`

Gateway:
1. Command: `python -m uvicorn companion_app.server:app --app-dir src --host 127.0.0.1 --port 13000`
2. Env:
   - `COMPANION_HOST_BASE_URL=http://127.0.0.1:18082`
   - `COMPANION_API_KEY=companion-key`
   - `COMPANION_GATEWAY_REQUIRE_LOOPBACK=true`
   - `COMPANION_GATEWAY_REQUIRE_SAME_ORIGIN=true`
   - `COMPANION_TIMEOUT_SECONDS=45`

## 3. Observed Results

| Step | Observed path | Observed result | Status |
| --- | --- | --- | --- |
| compat_mode_host_companion_status_with_core_key | degraded | partial success | 200 |
| compat_mode_host_companion_status_with_companion_key | degraded | partial success | 200 |
| host_core_route_with_companion_key_rejected | primary | success | 403 |
| gateway_status | degraded | partial success | 200 |
| gateway_config_patch | primary | success | 200 |
| gateway_config_get | primary | success | 200 |
| gateway_chat | degraded | partial success | 200 |
| gateway_voice_control_start | primary | success | 200 |
| gateway_voice_control_submit | primary | success | 200 |
| gateway_voice_control_stop | primary | success | 200 |
| gateway_cross_origin_chat_block | primary | success | 403 |
| strict_mode_host_companion_status_with_core_key_rejected | primary | success | 403 |
| strict_mode_host_companion_status_with_companion_key | degraded | partial success | 200 |
| strict_mode_host_core_route_with_core_key | primary | success | 200 |
| strict_mode_gateway_status | degraded | partial success | 200 |

## 4. Degraded/Blocked Notes

Degraded (expected in this environment):
1. STT unavailable reported in status payload (`stt_available=false`, `text_only_degraded=true`).
2. Chat still succeeds in explicit text-only degraded mode.

Blocked:
1. None.

## 5. Raw Artifact Note

The machine-readable probe artifact was generated at:
1. `benchmarks/results/companion/ui_closeout/companion_ui_live_evidence_2026-03-09.json`

That path is ignored by repository policy (`benchmarks/results/**`); this document is the committed durable summary.
