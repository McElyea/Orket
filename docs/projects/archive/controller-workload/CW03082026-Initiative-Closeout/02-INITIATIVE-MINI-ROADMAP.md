# Controller Workload Initiative Mini-Roadmap (SDK-First)

Last updated: 2026-03-08
Status: Completed (Archived)
Owner: Orket Core

## Summary
Build a guarded Controller Workload capability where orchestration logic is SDK-owned, child execution is runtime-governed, and all child calls run through `ExtensionManager`.

Locked v0:
1. SDK-only children
2. Sequential execution
3. Hybrid caps (payload request + runtime hard caps)
4. Stable fail-closed controller behavior with deterministic observability and parity checks

Final execution pointer (archived):
1. `docs/projects/archive/controller-workload/CW03082026-Phase2D/05-IMPLEMENTATION-PLAN-Phase-2D.md`

Final requirements slice (archived):
1. `docs/projects/archive/controller-workload/CW03082026-Phase2D/04-REQUIREMENTS-Phase-2D.md`

Final planning handoff (archived):
1. `docs/projects/archive/controller-workload/CW03082026-Phase2D/07-V1-PLANNING-HANDOFF.md`

Naming convention for continuing slices:
1. Requirements: `NN-REQUIREMENTS-Phase-<phase>.md`
2. Implementation plan: `NN-IMPLEMENTATION-PLAN-Phase-<phase>.md`

Phase status:
1. Phase 1 (steps 1-10): completed and archived under `docs/projects/archive/controller-workload/CW03082026/`
2. Phase 2 (steps 11-22): completed and archived under `docs/projects/archive/controller-workload/CW03082026-Phase2A/`, `docs/projects/archive/controller-workload/CW03082026-Phase2B/`, `docs/projects/archive/controller-workload/CW03082026-Phase2C/`, and `docs/projects/archive/controller-workload/CW03082026-Phase2D/`

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
11. Completed 2026-03-08: Added operator runbook (`docs/runbooks/controller-workload-operator.md`) and authoring guide (`docs/guides/controller-workload-authoring.md`).
12. Completed 2026-03-08: Hardened recursion/cycle/error handling and blocked run-result semantics in dispatcher/runtime models.
13. Completed 2026-03-08: Added controller observability helper + deterministic batch emission path with schema validation and fail-closed handling.
14. Completed 2026-03-08: Added controller replay/parity comparator + script path with deterministic mismatch reporting.
15. Completed 2026-03-08: Added controller parity checks to `.gitea/workflows/quality.yml` fail-closed gate.
16. Completed 2026-03-08: Added externalization bootstrap template scaffold and template guidance.
17. Completed 2026-03-08: Added external-repo bootstrap utility and verified install-path execution through integration tests.
18. Completed 2026-03-08: Published migration guidance with executable bootstrap/install/parity validation steps.
19. Completed 2026-03-08: Added environment rollout controls (`ORKET_CONTROLLER_ENABLED`, `ORKET_CONTROLLER_ALLOWED_DEPARTMENTS`) with blocked fail-closed behavior.
20. Completed 2026-03-08: Verified end-to-end external-style install-path execution through real `ExtensionManager.run_workload` integration flow.
21. Completed 2026-03-08: Ran reliability hardening pass with repeated controller test runs and published reliability report.
22. Completed 2026-03-08: Published v1 planning handoff packet for bounded parallelism and broader child-type support.

## Milestones
1. M1 Foundation Complete: steps 1-3.
2. M2 SDK + Runtime Core Complete: steps 4-8.
3. M3 Verified v0 Complete: steps 9-10.
4. M4 Externalization Complete: steps 16-20.
5. M5 v1 Readiness Complete: steps 21-22.

## Assumptions
- Active execution authority remains `docs/ROADMAP.md`, `docs/CONTRIBUTOR.md`, and `CURRENT_AUTHORITY.md`.
- Initial source bootstrap is `extensions/controller_workload`; long-term install target is external repositories.
- Canonical runtime entrypoints and canonical test command remain unchanged in this initiative.
