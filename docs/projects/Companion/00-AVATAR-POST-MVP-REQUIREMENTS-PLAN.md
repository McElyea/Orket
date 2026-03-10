# Companion Avatar Post-MVP Requirements Plan

Last updated: 2026-03-09
Status: Draft (Requirements Accepted for Planning)
Owner: Orket Core

## 1. Purpose

Define the post-MVP avatar requirements for Companion using the current architecture boundary:

1. Companion UI owns presentation and interaction.
2. Host API remains the only runtime/model/memory/voice authority seam.
3. Decorative/avatar assets never block core render.

This document is requirements-first and phase-oriented. It does not force a full implementation in one slice.

## 2. Authority Inputs

1. `docs/specs/COMPANION_UI_MVP_CONTRACT.md`
2. `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/11-COMPANION-CANONICAL-IMPLEMENTATION-PLAN.md`
3. `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/Building a Web Frontend for Chat + Lip-Synced Avatar Connected to a Python Backend.pdf`

## 2a. Authority Split

To prevent boundary drift, avatar behavior must respect the following authority split:

1. UI-local authority
   1. Avatar mode.
   2. Optional asset reference.
   3. Motion intensity and presentation preferences.
   4. Renderer selection and local degradation behavior.
2. Host-derived authority
   1. Conversation lifecycle/status events.
   2. TTS playback lifecycle exposed through the current UI/Host seam.
   3. Optional avatar control-plane events such as expression or gesture signals.
3. Playback-derived authority
   1. Baseline mouth motion must be derived in the UI layer from actual currently playing TTS audio playback or decoded playback buffer analysis.
   2. Lip-sync behavior must not depend on provider internals, token timing, model timing, or backend-only runtime state.

## 2b. Versioned UI Settings Contract

Avatar presentation settings must use a versioned UI-local contract so persistence can evolve without ambiguity.

Canonical persisted shape for this lane:

1. `avatar_prefs_v1`

Minimum fields:

1. `version`
2. `mode`
3. `renderer`
4. `asset_ref`
5. `motion_profile`
6. `fallback_policy`

Rules:

1. `avatar_prefs_v1` is UI-local state only and must not become backend/provider/runtime configuration.
2. Unknown or invalid settings payloads must fail closed to safe defaults and must not break render.
3. Future schema revisions must provide an explicit migration path from the immediately previous supported version before use.
4. Migration failure must revert to safe defaults and emit a non-fatal observability event.
5. Settings migration must not require network access, backend calls, or provider knowledge.
6. `fallback_policy` is an invariant for this lane and is not user-toggleable.

A concrete contract shape for the implementation plan:

```ts
type AvatarPrefsV1 = {
  version: "avatar_prefs_v1";
  mode: "off" | "fallback" | "avatar";
  renderer: "fallback" | "vrm";
  asset_ref: string | null;
  motion_profile: "default" | "reduced";
  fallback_policy: "always_safe";
};
```

## 3. Problem Statement

Companion currently has a resilient presence placeholder, but no production avatar pipeline for asset loading, animation orchestration, lip-sync, and expression channels.

We need an implementation path that:

1. upgrades presence quality quickly,
2. preserves Host API authority and security boundaries,
3. remains performant and failure-tolerant on local hardware.

## 4. Scope

### 4.1 In Scope

1. Avatar renderer seam in UI with fallback-first behavior.
2. Optional avatar asset configuration and loading.
3. Speaking/listening visual lifecycle tied to existing voice/TTS state.
4. Lip-sync baseline driven by current TTS playback audio analysis.
5. Extensible control-plane event model for future expression/gesture signals.
6. Verification standards for behavior, resilience, and performance.

### 4.2 Out of Scope (This Lane)

1. Full emotion engine.
2. Full viseme-quality lip-sync pipeline on day one.
3. Mandatory WebRTC migration.
4. Premium art/motion polish pass.
5. Backend model/runtime ownership changes.

## 5. Functional Requirements

### FR-1 Avatar Render Resilience

1. Presence panel must render even when no avatar asset is configured.
2. Asset load failure must degrade to fallback without breaking chat, settings, voice, memory, or status surfaces.
3. Avatar renderer errors must be contained and surfaced as non-fatal UI notices.
4. Avatar renderer failures must be isolated to the avatar/presence region and must not unmount, reset, or corrupt parent Companion application state.
5. Renderer initialization failure must transition to `fallback_active` within the same session without requiring reload.

### FR-2 Avatar Renderer Abstraction

1. UI must use a renderer seam, with at minimum:
   1. fallback renderer,
   2. VRM-capable renderer.
2. Renderer selection must be a presentation setting and must not become runtime/provider state.
3. Renderer swaps must not require backend/provider changes.
4. Fallback renderer must consume the same normalized avatar state contract as non-fallback renderers.
5. The renderer seam must expose an explicit contract for:
   1. normalized state input,
   2. lifecycle hooks,
   3. asset loading,
   4. control-event ingestion,
   5. suspension/degradation,
   6. error reporting.
6. Renderer implementations must be replaceable without changing:
   1. Host API contract,
   2. state coordinator behavior,
   3. settings persistence format,
   4. control-plane event envelope.

### FR-3 Avatar Configuration Controls

1. UI must expose avatar mode and optional asset reference in the bottom settings tray.
2. Settings must persist locally and restore on reload.
3. Invalid or unsupported asset values must fail closed to fallback renderer.
4. Avatar settings must remain independent from provider/runtime configuration.
5. Asset configuration must not introduce credentials, secrets, or provider-coupled settings.
6. Persisted avatar settings must use the versioned `avatar_prefs_v1` contract for this lane.
7. Settings reads must validate schema before use.
8. Settings migration must occur before renderer initialization.

### FR-4 Conversation/Voice Lifecycle Mapping

1. Avatar state must support at least:
   1. `idle`,
   2. `listening`,
   3. `thinking`,
   4. `speaking`.
2. The primary avatar lifecycle state must be single-valued at any instant.
3. State transitions must be deterministic from observable UI and Host events.
4. Impossible state combinations must be prevented by a single state coordinator.
5. State priority must be deterministic when competing signals exist.
6. Default priority order is:
   1. `speaking`,
   2. `listening`,
   3. `thinking`,
   4. `idle`,
   unless a documented product rule supersedes this ordering.
7. `thinking` may only be entered from:
   1. observable request-in-flight state between user submit and assistant response completion, or
   2. an explicit Host API status event.
8. `thinking` must not be inferred from elapsed time, inactivity, lack of movement, or speculative heuristics.
9. Fallback renderer must continue to reflect normalized lifecycle state even when richer rendering is unavailable.
10. Lifecycle transitions must follow a documented transition table.
11. Interruption and barge-in handling must be deterministic and must not rely on heuristic animation timing.
12. Default lifecycle precedence is:
    1. `speaking`,
    2. `listening`,
    3. `thinking`,
    4. `idle`.
13. Exception: explicit barge-in intent may preempt `speaking` only after playback interruption is observed or acknowledged by the current playback path.

### FR-5 Lip-Sync Baseline

1. Baseline lip-sync must work with the current TTS playback path.
2. Mouth movement may start as amplitude-driven using Web Audio analysis plus smoothing.
3. Mouth animation must be driven by actual audio playback activity or decoded playback buffer analysis.
4. Lip-sync must not be driven by token timing, response timing, estimated speech duration, or simulated speech heuristics.
5. Lip-sync failure must not block TTS playback, audio completion, or chat progression.
6. Lip-sync stop/start behavior must track playback start/end truthfully, including interruption and cancellation paths.
7. Lip-sync start must be keyed from actual playback start, not response generation start.
8. Lip-sync stop must be keyed from actual playback end/interruption/cancel, not estimated clip duration.
9. Continuous mouth motion must not continue after playback truth has ended.

### FR-6 Extensible Expression Control

1. UI must be ready to consume optional control-plane events such as:
   1. `speech.start`,
   2. `speech.end`,
   3. `avatar.expression`,
   4. `avatar.gesture`.
2. Event processing must remain additive; absent events must not break baseline behavior.
3. Event contract must remain backend-agnostic and provider-agnostic.
4. Expression or gesture events must not be allowed to violate core lifecycle invariants.
5. Control-plane events must use a versioned envelope.
6. Minimum envelope fields for this lane are:
   1. `type`,
   2. `version`,
   3. `session_id`,
   4. `ts`,
   5. `idempotency_key`.
7. Event ingestion must be idempotency-safe at the envelope level.
8. Unknown event types must be ignored safely without breaking baseline behavior.
9. Unknown event versions must fail closed for that event only and must not break renderer/state coordinator operation.

### FR-7 Security and Boundary Preservation

1. Avatar logic must not directly call provider runtimes.
2. Host API remains the only runtime authority.
3. No credentials or secrets may be introduced into avatar asset/config paths.
4. Default asset selection must be local-only for this lane unless an explicit allowlist policy is later approved.
5. Optional non-local asset loading, if ever enabled, must be governed by a constrained allowlist and explicit user intent.
6. Credentialed fetch is prohibited for avatar assets.
7. Scriptable payloads are prohibited for avatar assets and related config inputs.
8. Asset loading must not introduce:
   1. script execution,
   2. credential forwarding,
   3. backend secret exposure,
   4. provider/runtime coupling.
9. Invalid, remote-disallowed, or policy-rejected asset references must fail closed to fallback renderer.

## 6. Non-Functional Requirements

### NFR-1 Performance

1. Performance verification for this lane must use a declared reference mid-tier hardware profile in the implementation plan.
2. On the reference mid-tier profile at default settings:
   1. avatar-enabled operation must maintain >=45 FPS average during a 60-second idle run,
   2. avatar-enabled operation must maintain >=45 FPS average during a 60-second speaking run,
   3. avatar enablement must add no more than 250 ms to cold-start time-to-interactive versus avatar-disabled baseline.
3. During a 60-second speaking run on the reference profile:
   1. average additional CPU utilization attributable to the avatar subsystem must remain within the declared ceiling,
   2. average additional GPU utilization attributable to the avatar subsystem must remain within the declared ceiling.
4. Initial execution ceilings for this lane are:
   1. <=20% additional CPU utilization,
   2. <=35% additional GPU utilization,
   measured at the Companion process level on the reference profile.
5. Heavy assets must load lazily and must not block initial UI interactivity.
6. Under resource pressure, degradation must occur in this order unless a documented implementation rule improves safety:
   1. reduce lip-sync update frequency,
   2. disable secondary expression layers,
   3. throttle renderer update cadence,
   4. activate fallback renderer.
7. Performance failure must degrade presentation quality before it degrades core chat, voice, or settings usability.

### NFR-2 Accessibility

1. Core chat workflow must remain keyboard-usable when avatar is enabled.
2. Motion intensity must remain calm and non-intrusive.
3. Avatar-only signals must not be the sole status channel for critical state.
4. Reduced-motion behavior must be explicitly supported through `motion_profile = reduced`.
5. In reduced-motion mode:
   1. idle bobbing, secondary motion loops, and decorative gesture loops must be disabled,
   2. listening and thinking must use static or near-static presentation plus non-motion status cues,
   3. speaking may use only minimal mouth-open change or a low-motion equivalent cue,
   4. continuous animation update cadence for speaking must be capped by implementation policy and must not rely on high-frequency motion to convey status,
   5. critical state must remain understandable without motion alone.

### NFR-3 Licensing and Asset Governance

1. Engine/library license and model/content license must be treated separately.
2. Avatar asset usage must record redistribution constraints where applicable.
3. Incompatible or restricted assets must not be treated as default distributable content.
4. No default or demo avatar asset may be shipped without explicit recorded license terms and redistribution status.
5. Demo assets used for development, screenshots, or internal testing must be distinguished from distributable product defaults.

### NFR-4 Observability

1. Emit structured non-fatal avatar lifecycle and error events for debugging.
2. Record degraded states explicitly, including `fallback_active` and `asset_load_failed`.
3. Logs must remain free of sensitive input content where not required.
4. Minimum baseline event vocabulary must include:
   1. `avatar.renderer_selected`,
   2. `avatar.asset_load_started`,
   3. `avatar.asset_load_succeeded`,
   4. `avatar.asset_load_failed`,
   5. `avatar.fallback_activated`,
   6. `avatar.state_changed`,
   7. `avatar.lipsync_started`,
   8. `avatar.lipsync_failed`,
   9. `avatar.lipsync_stopped`.
5. Observability routing for this lane must default to:
   1. structured client-side diagnostic sink,
   2. developer console in debug/dev modes,
   3. optional summarized Host-facing diagnostic path only where explicitly approved.
6. High-frequency raw animation data, audio amplitude streams, and continuous frame-by-frame updates must not be logged as normal observability events.
7. Sampling/default emission rules:
   1. failures and degradation events are unsampled,
   2. `avatar.state_changed` emits only on actual state transition,
   3. start/stop events emit once per lifecycle instance,
   4. repeated identical non-fatal warnings must be rate-limited.
8. Retention defaults for this lane must be explicit in the implementation plan.
9. Default retention policy target for this lane is short-lived diagnostic retention, not indefinite storage.
10. Redaction defaults must exclude:
    1. user message content,
    2. prompt content,
    3. raw audio payloads,
    4. secrets,
    5. credential-bearing asset references,
    6. query-string credentials or tokens in logged asset identifiers.

## 7. Delivery Phases

### Phase A: Foundation (Lowest Risk)

1. Implement UI renderer abstraction.
2. Add settings for avatar mode and optional asset.
3. Preserve fallback-first render invariants.
4. Add containment boundary and normalized state contract for fallback and non-fallback renderers.

Acceptance:

1. Missing or invalid assets never break render.
2. Settings persist and restore.
3. Renderer init/load failure activates fallback in-session without reload.
4. Avatar-region failure does not reset parent application state.

### Phase B: Speaking Presence Baseline

1. Bind lifecycle state `idle/listening/thinking/speaking` to existing UI/Host events.
2. Add amplitude-driven mouth-open baseline from current TTS playback path.
3. Ensure lip-sync derives from actual playback activity rather than simulated timing.

Acceptance:

1. Speaking animation triggers reliably on TTS playback.
2. TTS works even if lip-sync loop fails.
3. Playback interruption/cancel paths stop mouth activity correctly.
4. `thinking` is entered only from observable in-flight or Host status truth.

### Phase C: Expression Control Events

1. Add optional event contract ingestion for expression and gesture updates.
2. Keep compatibility when no expression events are produced.
3. Prevent expression/gesture signals from violating lifecycle truth.

Acceptance:

1. Event-driven expressions blend without blocking chat or audio loops.
2. No regression in fallback behavior.
3. Lifecycle truth remains deterministic under competing signals.

### Phase D: Transport Upgrade Decision Gate

1. Reassess audio transport only after baseline quality and performance evidence exists.
2. Upgrade to WebRTC only if latency or quality targets cannot be met with the current path.

Acceptance:

1. Decision is documented with measured evidence.
2. No premature transport complexity is adopted.

## 8. Verification Plan

1. Unit and contract tests for:
   1. avatar state transitions,
   2. state priority ordering,
   3. fallback activation rules,
   4. renderer seam invariants.
2. Integration tests for:
   1. TTS playback plus lip-sync baseline path,
   2. interruption/cancellation correctness,
   3. fallback behavior under renderer failure.
3. UI behavior tests for:
   1. settings persistence,
   2. degraded rendering,
   3. parent state preservation after avatar failure.
4. Live verification:
   1. asset-missing path,
   2. asset-load failure path,
   3. speaking path with TTS,
   4. fallback path with all core controls still functional,
   5. interruption/cancel speaking path,
   6. reduced-motion or low-motion validation pass.
5. Reduced-motion live verification:
   1. idle state shows no continuous decorative looping motion,
   2. listening and thinking remain visibly distinct without requiring animation,
   3. speaking remains perceptible with minimal motion,
   4. all core controls remain fully usable with reduced motion enabled.

## 9. Risks and Mitigations

1. Risk: asset/license mismatch.
   1. Mitigation: explicit license validation gate for default and demo assets.
2. Risk: renderer performance regressions.
   1. Mitigation: lazy loading, degradation policy, and measurable performance budgets in the verification gate.
3. Risk: complexity drift from premature transport migration.
   1. Mitigation: keep WebRTC behind the Phase D decision gate.
4. Risk: false-presence behavior that appears animated but does not reflect real playback/state truth.
   1. Mitigation: require observable-state-driven lifecycle and playback-derived lip-sync only.
5. Risk: renderer failure cascades into broader UI instability.
   1. Mitigation: isolate avatar failures to avatar-region boundaries and force in-session fallback activation.

## 10. Exit Criteria for This Requirements Lane

1. Requirements are accepted by product and engineering for execution.
2. A canonical implementation plan is created for the first executable phase.
3. `docs/ROADMAP.md` points to the selected execution plan path when execution starts.
4. The first executable implementation plan must include:
   1. normalized avatar state machine,
   2. lifecycle transition table including interruption/barge-in precedence,
   3. renderer seam contract,
   4. versioned `avatar_prefs_v1` settings contract and migration rules,
   5. degraded/fallback activation rules,
   6. control-plane event envelope versioning,
   7. reduced-motion behavior contract,
   8. observability routing, sampling, retention, and redaction defaults,
   9. measurable performance test procedure for the declared reference hardware profile.

## Appendix A. Renderer Seam Interface Contract

Minimum renderer seam contract for this lane:

```ts
type NormalizedAvatarState = {
  primary_state: "idle" | "listening" | "thinking" | "speaking";
  motion_profile: "default" | "reduced";
  mouth_open: number; // 0.0 - 1.0
  fallback_active: boolean;
  asset_ref: string | null;
};

type AvatarControlEventEnvelopeV1 = {
  type: string;
  version: "avatar_event_v1";
  session_id: string;
  ts: string; // ISO-8601
  idempotency_key: string;
  payload: Record<string, unknown>;
};

interface AvatarRenderer {
  id: "fallback" | "vrm" | string;
  init(): Promise<void>;
  loadAsset(assetRef: string | null): Promise<void>;
  applyState(state: NormalizedAvatarState): void;
  applyControlEvent(event: AvatarControlEventEnvelopeV1): void;
  suspend(reason: "perf" | "hidden" | "degraded"): void;
  resume(): void;
  dispose(): Promise<void>;
}
```

Error contract:

1. `init()` failure must trigger in-session fallback activation.
2. `loadAsset()` failure must not break parent application state.
3. `applyState()` and `applyControlEvent()` failures must be contained to the avatar region and surfaced as non-fatal errors.
4. Any renderer error must be observable and must not force backend/provider changes.

## Appendix B. Lifecycle Transition Table

| Current State | Observable Event | Next State | Notes |
|---|---|---|---|
| idle | mic capture started / listening entered | listening | Deterministic UI/Host event only |
| idle | request submitted / Host processing started | thinking | No heuristic thinking |
| idle | TTS playback started | speaking | Playback truth wins |
| listening | request submitted | thinking | Listening ends when request is committed |
| listening | TTS playback started | speaking | Speaking takes precedence |
| thinking | TTS playback started | speaking | Playback truth wins |
| thinking | request completed with no playback | idle | No fake speaking |
| speaking | TTS playback ended and no pending request | idle | Normal completion |
| speaking | TTS playback interrupted and mic capture started | listening | Explicit barge-in path |
| speaking | TTS playback interrupted and request still in flight | thinking | Only if Host/UI still indicates in-flight |
| any | renderer failure / asset failure | same logical state with fallback renderer active | Visual degradation only |
| any | reduced-motion enabled | same logical state | Presentation changes only |

Barge-in rule:

1. While `speaking`, explicit user interruption creates an interrupt intent.
2. `speaking` remains authoritative until playback interruption is observed or acknowledged.
3. After interruption truth is observed:
   1. transition to `listening` if mic capture is active,
   2. otherwise transition to `thinking` only if a valid in-flight state exists,
   3. otherwise transition to `idle`.

## Appendix C. Control-Plane Event Envelope

Canonical minimum envelope for this lane:

```ts
type AvatarControlEventEnvelopeV1 = {
  type: string;
  version: "avatar_event_v1";
  session_id: string;
  ts: string; // ISO-8601
  idempotency_key: string;
  payload: Record<string, unknown>;
};
```

Rules:

1. `session_id` must be opaque and non-secret.
2. `ts` must represent event production time.
3. `idempotency_key` must be stable for retried delivery of the same event.
4. Payload schemas may evolve by event type, but the envelope must remain stable within a version.
