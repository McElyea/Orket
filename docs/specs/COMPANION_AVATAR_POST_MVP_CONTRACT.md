# Companion Avatar Post-MVP Contract (v1)

Last updated: 2026-03-09
Status: Draft (planning authority)
Owner: Orket Core
Source requirements: `docs/projects/Companion/00-AVATAR-POST-MVP-REQUIREMENTS-PLAN.md`
Related UI authority: `docs/specs/COMPANION_UI_MVP_CONTRACT.md`

## 1. Purpose

Define durable avatar contracts for Companion post-MVP execution while preserving the existing Host API authority boundary.

This contract is implementation-facing authority. It does not require one-shot delivery of all avatar features.

## 2. Boundary and Authority

1. Companion UI owns presentation, interaction flow, and local presentation state.
2. Host API remains the only runtime/model/memory/voice authority seam.
3. Avatar/presence assets are optional and never allowed to block core render.
4. Companion UI must not call provider runtimes directly.

## 3. Versioned UI Settings Contract

Canonical persisted contract for this lane:

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

Rules:
1. `avatar_prefs_v1` is UI-local only.
2. Settings schema must be validated before use.
3. Migration runs before renderer initialization.
4. Unknown/invalid payloads fail closed to safe defaults.
5. Migration failure falls back to safe defaults and emits a non-fatal observability event.
6. `fallback_policy` is invariant for this lane and not user-toggleable.

## 4. Normalized Avatar State Contract

```ts
type NormalizedAvatarState = {
  primary_state: "idle" | "listening" | "thinking" | "speaking";
  motion_profile: "default" | "reduced";
  mouth_open: number; // 0.0 - 1.0
  fallback_active: boolean;
  asset_ref: string | null;
};
```

Lifecycle precedence:
1. `speaking`
2. `listening`
3. `thinking`
4. `idle`

Exception:
1. explicit barge-in may preempt `speaking` only after playback interruption is observed/acknowledged by the playback path.

Lifecycle transition table:

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

## 5. Renderer Seam Contract

```ts
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

Renderer error contract:
1. `init()` failure triggers in-session fallback activation.
2. `loadAsset()` failure must not break parent app state.
3. `applyState()` and `applyControlEvent()` failures stay contained to avatar region and surface as non-fatal errors.
4. Renderer replacement must not require Host API, coordinator, settings, or envelope changes.

## 6. Lip-Sync Baseline Contract

1. Lip-sync is driven by actual playback truth (playback activity or decoded playback buffer analysis).
2. Lip-sync start keys from actual playback start, not response generation start.
3. Lip-sync stop keys from actual playback end/interruption/cancel, not estimated clip duration.
4. Lip-sync failure must not block TTS playback or chat progression.

## 7. Control-Plane Event Envelope Contract

Canonical envelope:

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
1. envelope ingestion must be idempotency-safe.
2. unknown event types are ignored safely.
3. unknown event versions fail closed for that event only.
4. `session_id` is opaque and non-secret.
5. payload schema is event-type-specific; envelope remains stable within `avatar_event_v1`.

## 8. Asset and Security Policy

1. default asset selection is local-only for this lane.
2. non-local assets are out of scope unless explicitly allowlisted later.
3. credentialed fetch for avatar assets is prohibited.
4. scriptable payloads are prohibited for avatar assets/config.
5. invalid/disallowed assets fail closed to fallback renderer.

## 9. Accessibility and Reduced Motion Contract

Reduced motion is explicit via `motion_profile = "reduced"`.

In reduced-motion mode:
1. disable idle bobbing and decorative loop motion.
2. listening and thinking remain distinguishable without motion-only cues.
3. speaking uses minimal mouth-open change or low-motion equivalent cue.
4. critical state remains understandable without animation.

## 10. Observability Contract

Baseline vocabulary:
1. `avatar.renderer_selected`
2. `avatar.asset_load_started`
3. `avatar.asset_load_succeeded`
4. `avatar.asset_load_failed`
5. `avatar.fallback_activated`
6. `avatar.state_changed`
7. `avatar.lipsync_started`
8. `avatar.lipsync_failed`
9. `avatar.lipsync_stopped`

Emission rules:
1. failure and degradation events are unsampled.
2. `avatar.state_changed` emits only on actual state transition.
3. lifecycle start/stop emits once per lifecycle instance.
4. repeated identical non-fatal warnings are rate-limited.
5. high-frequency animation/amplitude streams are never logged as normal events.

Redaction defaults:
1. no user message content
2. no prompt content
3. no raw audio payloads
4. no secrets or credential-bearing identifiers
5. no query-string tokens in logged asset ids

## 11. Performance Contract (Lane Budgets)

Reference-profile budgets:
1. avatar-enabled idle run (60s): average >=45 FPS
2. avatar-enabled speaking run (60s): average >=45 FPS
3. avatar-enabled cold start adds <=250 ms TTI versus avatar-disabled baseline
4. avatar-attributable additional CPU ceiling: <=20%
5. avatar-attributable additional GPU ceiling: <=35%

Degradation order:
1. reduce lip-sync update frequency
2. disable secondary expression layers
3. throttle renderer update cadence
4. activate fallback renderer

## 12. Compatibility and Evolution

1. Future settings schemas must migrate from the immediately previous supported version.
2. Future envelope versions may extend payload semantics while preserving explicit versioning.
3. This contract may be revised with new versioned sections; breaking changes require migration and rollback notes in the associated implementation plan.
