# Controller Workload Initiative Mini-Roadmap (SDK-First)

Last updated: 2026-03-08
Status: Active
Owner: Orket Core

## Summary
Build a guarded Controller Workload capability where orchestration logic is SDK-owned, child execution is runtime-governed, and all child calls run through `ExtensionManager`.

Locked v0:
1. SDK-only children
2. Sequential execution
3. Hybrid caps (payload request + runtime hard caps)
4. Active lane in Priority Now

## Next 10 Steps
1. Bootstrap initiative lane in `docs/projects/controller-workload/` and register in roadmap.
2. Write `01-REQUIREMENTS.md` with explicit v0 decisions, non-goals, and acceptance gates.
3. Extract stable contract to `docs/specs/CONTROLLER_WORKLOAD_V1.md`.
4. Add SDK controller primitives in `orket_extension_sdk/controller.py` and export them.
5. Define runtime cap controls (depth/fanout/timeout) and deterministic clamp rules.
6. Add controller dispatcher in `orket/extensions/` that calls `ExtensionManager.run_workload`.
7. Enforce v0 guards (SDK-only children, depth/fanout/time caps, stable denial codes).
8. Implement deterministic sequential child executor.
9. Add deterministic provenance chain expansion for controller-child runs.
10. Add unit/contract/integration tests and phase evidence report.

## Remaining Steps After 10
11. Add operator authoring/runbook docs.
12. Harden recursion/cycle detection behavior and error schema.
13. Add observability metrics/events for controller runs.
14. Add protocol replay and ledger parity checks for controller-child runs.
15. Add CI conformance gate for controller contracts/integration tests.
16. Add bootstrap template for externalizing `extensions/controller_workload`.
17. Migrate controller extension to external repo install path.
18. Publish migration guidance for in-repo bootstrap to external extension.
19. Add environment rollout controls/feature flags for controller enablement.
20. Run live end-to-end integration verification with external install path.
21. Run reliability hardening cycle (flake, retry boundaries, failure taxonomy).
22. Cut v1 planning for bounded parallel and broader child-type support.

## Milestones
1. M1 Foundation Complete: steps 1-3.
2. M2 SDK + Runtime Core Complete: steps 4-8.
3. M3 Verified v0 Complete: steps 9-10.
4. M4 Externalization Complete: steps 16-20.
5. M5 v1 Readiness: steps 21-22.

## Assumptions
- Active execution authority remains `docs/ROADMAP.md`, `docs/CONTRIBUTOR.md`, and `CURRENT_AUTHORITY.md`.
- Initial source bootstrap is `extensions/controller_workload`; long-term install target is external repositories.
- Canonical runtime entrypoints and canonical test command remain unchanged in this initiative.
