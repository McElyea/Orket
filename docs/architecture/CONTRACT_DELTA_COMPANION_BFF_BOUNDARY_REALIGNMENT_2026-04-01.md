# Contract Delta - Companion BFF Boundary Realignment

## Summary
- Change title: Companion product API ownership moves to the external BFF
- Owner: Orket Core
- Date: 2026-04-01
- Affected contract(s): `docs/specs/COMPANION_UI_MVP_CONTRACT.md`, `docs/API_FRONTEND_CONTRACT.md`, `docs/RUNBOOK.md`, `docs/SECURITY.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: Orket core owned Companion-named host routes and Companion-scoped host auth, while the external gateway mostly proxied those host routes.
- Proposed behavior: Companion product routes live only in the external Companion gateway/BFF under `/api/*`; Orket host exposes only generic extension runtime routes under `/v1/extensions/{extension_id}/runtime/*` and uses the normal `ORKET_API_KEY` posture.
- Why this break is required now: It removes Companion-specific host routing and auth knowledge from Orket core, makes the BFF the only product API surface, and aligns the active contract set with the shipped implementation.

## Migration Plan
1. Compatibility window: none in core; old host Companion routes are removed as part of the same cutover while the external BFF keeps the outward `/api/*` product surface stable.
2. Migration steps:
   - move product orchestration into the Companion BFF
   - mount only the generic extension runtime router in Orket core
   - repoint Companion BFF host calls to `/v1/extensions/{extension_id}/runtime/*`
   - remove Companion-scoped host auth handling
   - update active specs, operator docs, and authority snapshots
3. Validation gates:
   - targeted Orket integration tests for generic extension runtime routing and auth
   - targeted Companion BFF route tests against mocked host-runtime client seams
   - cross-process live proof with Orket host plus Companion gateway using the generic host runtime path

## Rollback Plan
1. Rollback trigger: generic extension runtime cutover blocks Companion BFF product flows or live proof fails.
2. Rollback steps:
   - restore the previous host Companion router and auth branch
   - repoint the Companion BFF host client back to the removed host routes
   - rerun route, auth, and live proof checks
3. Data/state recovery notes: Companion config and history state remain serialized through generic host memory; no data migration is required to roll back route ownership.

## Versioning Decision
- Version bump type: none
- Effective version/date: 2026-04-01
- Downstream impact: Companion operators must use the BFF `/api/*` product surface and the host generic extension runtime surface; Companion-scoped host API keys are no longer admitted.
