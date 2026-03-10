# Companion Avatar Phase B Implementation Plan (Speaking Presence Baseline)

Last updated: 2026-03-09
Status: Draft (queued)
Owner: Orket Core
Canonical lane plan: `docs/projects/Companion/01-AVATAR-POST-MVP-CANONICAL-IMPLEMENTATION-PLAN.md`
Contract authority: `docs/specs/COMPANION_AVATAR_POST_MVP_CONTRACT.md`
Depends on: Phase A foundation completion

## 1. Objective

Implement truthful avatar lifecycle behavior and playback-derived lip-sync baseline:
1. deterministic lifecycle state coordinator,
2. barge-in precedence,
3. actual playback truth as speaking/lipsync authority.

## 2. Scope Deliverables

1. Normalized lifecycle coordinator implementing `idle/listening/thinking/speaking`.
2. Transition table and precedence enforcement including barge-in rule.
3. Amplitude-driven mouth-open baseline driven by active playback path.
4. Reliable stop semantics on end/interruption/cancel.
5. Reduced-motion compliant speaking/listening/thinking cues.

## 3. Detailed Tasks

### Workstream B1 - Lifecycle State Coordinator
Tasks:
1. Implement deterministic coordinator from observable UI/Host/playback events only.
2. Enforce single-valued primary state and precedence order.
3. Implement explicit barge-in interrupt intent handling with playback acknowledgment requirement.

Acceptance:
1. no impossible state combinations are emitted.
2. `thinking` is entered only from in-flight/Host-status truth.
3. speaking remains authoritative until interruption truth is observed.

### Workstream B2 - Lip-Sync Baseline on Playback Truth
Tasks:
1. Bind lipsync start to actual playback start signal.
2. Drive mouth-open by playback amplitude/buffer analysis with smoothing.
3. Bind lipsync stop to playback end/interruption/cancel.
4. Guard against orphan motion loops after playback truth ends.

Acceptance:
1. no lipsync activity when no playback is active.
2. cancellation/interruption immediately halts speaking motion.
3. lipsync failure does not stop TTS playback.

### Workstream B3 - Reduced-Motion Behavior
Tasks:
1. Implement reduced-motion policy in lifecycle visualization.
2. Disable decorative continuous loops in reduced mode.
3. Preserve state distinguishability without motion-only cues.

Acceptance:
1. reduced mode remains functionally informative.
2. core chat/voice controls remain fully usable.

## 4. Verification Plan

Unit/Contract:
1. lifecycle transition table invariants.
2. precedence and barge-in rules.

Integration:
1. TTS playback + lipsync start/stop truth.
2. interruption/cancel behavior correctness.
3. degraded fallback path with lifecycle continuity.

UI behavior:
1. auto-scroll/state rendering remains stable during long chats and speaking updates.
2. reduced-motion visual behavior contract.

Live:
1. speaking path with actual TTS playback.
2. explicit user interruption while speaking.
3. request completes with no playback path.

## 5. Completion Gate

Phase B is complete when:
1. lifecycle transitions are deterministic and tested,
2. lipsync is tied to actual playback truth (not timing heuristics),
3. interruption/cancel paths behave correctly in live verification,
4. reduced-motion behavior is verified and non-breaking.
