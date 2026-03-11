# Companion Avatar Post-MVP Canonical Implementation Plan

Last updated: 2026-03-10
Status: In Progress (execution started)
Owner: Orket Core
Source requirements: `docs/projects/Companion/00-AVATAR-POST-MVP-REQUIREMENTS-PLAN.md`
Contract authority: `docs/specs/COMPANION_AVATAR_POST_MVP_CONTRACT.md`
Related UI authority: `docs/specs/COMPANION_UI_MVP_CONTRACT.md`

## 1. Objective

Deliver Companion avatar post-MVP in bounded phases that preserve:
1. Host API runtime authority,
2. fallback-first rendering resilience,
3. deterministic lifecycle truth tied to observable playback and UI/Host signals.

## 2. Delivery Model

Execution is phase-scoped with explicit acceptance gates:
1. Phase A: foundation and renderer seam
2. Phase B: lifecycle + speaking presence baseline
3. Phase C: expression/control-event ingestion
4. Phase D: transport upgrade decision gate

No phase expands backend runtime authority beyond current Host API semantics.

## 3. Plan Set

This canonical plan delegates executable detail to:
1. `docs/projects/Companion/02-IMPLEMENTATION-PLAN-AVATAR-PHASE-A-FOUNDATION.md`
2. `docs/projects/Companion/03-IMPLEMENTATION-PLAN-AVATAR-PHASE-B-SPEAKING-PRESENCE.md`
3. `docs/projects/Companion/04-IMPLEMENTATION-PLAN-AVATAR-PHASE-C-CONTROL-EVENTS.md`
4. `docs/projects/Companion/05-IMPLEMENTATION-PLAN-AVATAR-PHASE-D-TRANSPORT-DECISION.md`

## 3a. Execution Status Snapshot

Completed:
1. [x] Phase A foundation workstreams implemented in the Companion extension runtime (`avatar_prefs_v1`, renderer seam, fallback-safe asset policy, settings controls).
2. [x] Phase C envelope parser + idempotency dedupe (`avatar_event_v1`) with safe unknown-version/type handling.
3. [x] Phase C additive expression/gesture cue mapping implemented without changing lifecycle authority precedence.
4. [x] Phase C observability baseline vocabulary, warning rate-limiting, and payload redaction defaults implemented.
5. [x] Phase C optional connected-path control-event feed (`POST` publish + `GET` feed) implemented and live-verified.
6. [x] Phase D baseline harness entrypoint established and expanded to multi-run API latency aggregation with system-profile metadata for reproducible host+gateway probes.
7. [x] Phase B live speaking and interruption/cancel playback proof completed on real host+gateway+UI path.
8. [x] Phase D degraded-mode baseline evidence captured for TTS-unavailable path while chat remained usable.

Remaining:
1. [ ] Phase D performance measurement and transport decision gate.

## 4. Dependency and Order

Execution order is strict unless explicitly marked parallel in a phase plan:
1. Phase A -> Phase B -> Phase C -> Phase D

Critical path:
`A -> B -> D`

Rationale:
1. Phase B depends on Phase A renderer seam and state contracts.
2. Phase C is additive and must not regress Phase B baseline truth.
3. Phase D requires measured data from at least Phase B.

## 5. Core Deliverables

1. Versioned avatar settings persistence (`avatar_prefs_v1`) with migration handling.
2. Renderer seam with fallback and VRM-capable implementation boundary.
3. Deterministic avatar lifecycle state coordinator with transition table and barge-in precedence.
4. Playback-truth-driven lip-sync baseline integrated with existing TTS path.
5. Versioned control-plane event envelope ingestion with idempotency-safe processing.
6. Reduced-motion compliant behavior and observability defaults.
7. Evidence-backed transport decision (retain current path or escalate to WebRTC).

## 6. Verification Strategy

Required by phase:
1. Contract tests for settings schema, lifecycle transition invariants, envelope parsing, and renderer seam behavior.
2. Integration tests for TTS playback + lip-sync start/stop truth, interruption/cancel behavior, and fallback activation.
3. UI behavior tests for persistence restore, reduced-motion behavior, and avatar-region failure containment.
4. Live verification (non-mocked) for asset-missing, asset-failure, speaking path, interruption path, and fallback path.

Test-layer labeling policy:
1. each new/modified test must identify its layer as unit, contract, integration, or end-to-end in plan and PR reporting.

## 7. Governance and Boundary Controls

1. No provider-runtime direct calls from avatar UI code.
2. No credential-bearing or scriptable avatar asset loading.
3. Degradation preserves chat/voice/settings usability before presentation fidelity.
4. Unknown settings/event payloads fail closed without app-wide failure.

## 8. Execution Gate and Handoff

Lane execution is complete when:
1. Phase A-D acceptance gates are satisfied,
2. performance budgets are measured and documented on a declared reference profile,
3. transport decision is explicitly recorded with evidence,
4. roadmap lane pointer can move from future-hold to active completion/archive flow.

If execution is paused mid-lane:
1. roadmap continues to point to this canonical plan,
2. current active phase plan is marked in progress with blockers captured concretely.
