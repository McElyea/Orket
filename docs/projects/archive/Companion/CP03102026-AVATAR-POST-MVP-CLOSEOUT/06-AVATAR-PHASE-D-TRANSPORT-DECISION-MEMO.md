# Companion Avatar Phase D Transport Decision Memo

Last updated: 2026-03-10
Status: Active decision (retain current transport; no WebRTC escalation)
Owner: Orket Core
Canonical phase plan: `docs/projects/Companion/05-IMPLEMENTATION-PLAN-AVATAR-PHASE-D-TRANSPORT-DECISION.md`
Contract authority: `docs/specs/COMPANION_AVATAR_POST_MVP_CONTRACT.md`

## 1. Decision

Retain the current Companion transport path (Host API + local Companion gateway/UI) and do not open a WebRTC implementation lane at this time.

## 2. Evidence Snapshot (`2026-03-10`)

1. Live probe with `--model llama3.1:8b`, `--enable-piper`, and `--ui-interrupt-probe` on the real host+gateway+UI path:
   1. `status.http_status=200`, `status.body.tts_available=true`
   2. `chat.http_status=200` (`elapsed_ms=4164.18`)
   3. `voice_synthesize.body.ok=true` (`audio_b64_len=97624`)
   4. UI interruption probe passed (`ok=true`), with `speak_started=true`, `stop_playback_observed=true`, and `stop_playback_cleared=true`
   5. Browser timing sample: `navigation_ms.response_end=34.9`, `dom_content_loaded_end=48.8`, `load_event_end=49.3`, `raf_sample.fps=60.19`
2. Induced CPU-pressure run (16 local stress workers) on the same path:
   1. `system_metrics_before.cpu_total_percent=54.86`
   2. `system_metrics_after.cpu_total_percent=56.04`
   3. `status.http_status=200` with degraded flags still explicit
   4. `chat.http_status=200` (`elapsed_ms=4320.41`)
   5. `chat.body.config` returned (settings/config payload preserved under pressure)
3. Degraded-mode baseline has been captured separately: when TTS is unavailable, chat remained usable and voice path returned explicit `tts_unavailable`.

## 3. Assessment

1. Current evidence does not show a transport-driven failure that requires WebRTC migration.
2. Live interruption and degraded-path behavior remain functional on the existing path.
3. Under induced CPU pressure, the gateway and chat path stayed operational, and degradation stayed explicit rather than silent.

## 4. Remaining Evidence Gap

The following contract-grade measurement set is still pending before full Phase D closeout:
1. 60s avatar-disabled vs avatar-enabled comparison runs with explicit budget pass/fail mapping for:
   1. FPS (idle + speaking),
   2. TTI delta,
   3. avatar-attributable CPU uplift,
   4. avatar-attributable GPU uplift.

## 5. Reopen Triggers for WebRTC Lane

Open a scoped WebRTC lane only if one or more of these are observed with reproducible evidence:
1. Transport-attributable chat/voice reliability failure under normal local profile.
2. Transport path cannot maintain interruption/cancel responsiveness.
3. Contract budget failures are measured and attributable to the current transport path rather than provider/model selection.
