# Companion BFF-Only Cutover Closeout

Last updated: 2026-04-01

## Summary
1. Orket core no longer mounts Companion-named product routes.
2. Orket host now exposes the generic extension runtime surface under `/v1/extensions/{extension_id}/runtime/*`.
3. The external Companion gateway/BFF now owns outward `/api/*` product routes and translates them to the generic host runtime surface.

## Authority
1. Active Companion boundary contract: `docs/specs/COMPANION_UI_MVP_CONTRACT.md`
2. Active host API contract: `docs/API_FRONTEND_CONTRACT.md`
3. Active operator guidance: `docs/RUNBOOK.md`
4. Active security posture: `docs/SECURITY.md`
5. Active authority snapshot: `CURRENT_AUTHORITY.md`

## Historical Record
1. Archived migration plan: `docs/projects/archive/Companion/CP04012026-BFF-ONLY-CUTOVER/COMPANION_TRUE_BFF_ONLY_MIGRATION_PLAN.md`
