# Companion Avatar Phase A Implementation Plan (Foundation)

Last updated: 2026-03-10
Status: In Progress (implementation complete; phase closeout pending lane-level handshake)
Owner: Orket Core
Canonical lane plan: `docs/projects/Companion/01-AVATAR-POST-MVP-CANONICAL-IMPLEMENTATION-PLAN.md`
Contract authority: `docs/specs/COMPANION_AVATAR_POST_MVP_CONTRACT.md`

## 1. Objective

Implement the lowest-risk avatar foundation:
1. renderer abstraction seam,
2. versioned settings contract and migration path,
3. fallback-first resilience and failure containment.

## 2. Scope Deliverables

1. Versioned avatar settings persistence using `avatar_prefs_v1`.
2. Schema validation + migration-before-init flow.
3. Renderer seam contract implementation with fallback and VRM-capable paths.
4. Avatar-region error containment boundary.
5. Bottom settings tray controls for avatar mode, renderer, asset reference, and motion profile.

## 3. Detailed Tasks

### Workstream A1 - Settings Contract + Migration
Tasks:
1. Define `AvatarPrefsV1` type and defaults (`fallback_policy: "always_safe"`).
2. Add schema validator and migration entrypoint for persisted settings reads.
3. Fail closed to safe defaults on invalid/unknown payload.
4. Emit non-fatal observability event on migration failure.

Acceptance:
1. corrupted or unknown settings never break render.
2. migration runs before renderer initialization.
3. settings restore deterministically on reload.

### Workstream A2 - Renderer Seam Foundation
Tasks:
1. Implement normalized renderer interface and lifecycle hooks.
2. Implement fallback renderer consuming normalized state.
3. Implement VRM-capable adapter behind the same interface (feature-flagged or gated if needed).
4. Ensure `init()` and `loadAsset()` failures activate/retain fallback in-session.

Acceptance:
1. renderer swap does not require Host API changes.
2. fallback consumes same state contract as VRM path.
3. renderer failure is isolated to avatar region.

### Workstream A3 - Asset Policy and Failure Handling
Tasks:
1. Enforce local-only default asset policy.
2. Reject disallowed/invalid asset refs to fallback path.
3. Prohibit credentialed fetch and scriptable payload handling in avatar asset path.

Acceptance:
1. disallowed asset paths fail closed to fallback.
2. chat/settings/voice surfaces remain usable after avatar failures.

### Workstream A4 - UI Controls and Persistence UX
Tasks:
1. Expose avatar mode/renderer/asset/motion controls in bottom tray.
2. Keep settings strictly presentation-only and local.
3. Ensure reduced-motion selection is persisted and restored.

Acceptance:
1. settings edits persist and restore correctly.
2. controls do not alter provider/runtime config.

## 4. Verification Plan

Contract:
1. settings schema validation and migration tests.
2. renderer seam invariants and fallback-activation tests.

Integration:
1. asset-load failure path with fallback activation.
2. renderer init failure path with in-session fallback.

UI behavior:
1. settings persistence restore on reload.
2. parent state preservation after avatar renderer failure.

Live:
1. no-asset configured path.
2. invalid asset configured path.
3. renderer-failure injection path with fallback.

## 5. Completion Gate

Phase A is complete when:
1. settings contract/migration is live and tested,
2. renderer seam + fallback invariants are verified,
3. avatar failure containment is demonstrated in live verification,
4. bottom settings controls are present and persistence-correct.

## 6. Execution Checklist Snapshot

1. [x] Workstream A1 settings contract + migration.
2. [x] Workstream A2 renderer seam foundation.
3. [x] Workstream A3 asset policy and fail-closed handling.
4. [x] Workstream A4 UI controls and persistence UX.
5. [ ] Formal phase closeout/archive handshake in roadmap/docs set (pending while Phase B/C execution is still active in this lane).
