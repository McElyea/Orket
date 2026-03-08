# Controller Workload Phase 2 Implementation Plan

Last updated: 2026-03-08
Status: Completed (Archived Initiative Umbrella)
Owner: Orket Core
Source initiative roadmap: `docs/projects/archive/controller-workload/CW03082026-Initiative-Closeout/02-INITIATIVE-MINI-ROADMAP.md`
Contract authority: `docs/specs/CONTROLLER_WORKLOAD_V1.md`
Current requirements slice: `docs/projects/archive/controller-workload/CW03082026-Phase2D/04-REQUIREMENTS-Phase-2D.md`
Current phase implementation slice: `docs/projects/archive/controller-workload/CW03082026-Phase2D/05-IMPLEMENTATION-PLAN-Phase-2D.md`

## 1. Objective

Execute the final Phase 2 initiative slices: operational hardening, externalization path, rollout controls, reliability hardening, and v1 planning handoff while preserving Phase 1 runtime invariants.

Execution note:
1. This document was the initiative-level execution plan.
2. Execution proceeds in bounded, explicitly named slices.
3. Final bounded slice was Phase 2D, defined in `04-REQUIREMENTS-Phase-2D.md`.
4. Direct implementation authority for the final slice was `05-IMPLEMENTATION-PLAN-Phase-2D.md`.

Non-negotiable carry-forward invariants:
1. Child execution remains sequential unless a future spec explicitly supersedes v1.
2. Child dispatch authority remains `ExtensionManager.run_workload`.
3. Stable controller error-code surfaces remain authoritative.
4. Runtime behavior remains fail-closed.
5. Deterministic provenance/summary behavior remains required.

## 2. Scope (Mini-Roadmap Alignment)

This phase executes initiative mini-roadmap steps 11-21 and prepares step 22 planning input.

1. Operator authoring and runtime runbook docs.
2. Recursion/cycle behavior and error-schema hardening.
3. Observability metrics/events for controller runs.
4. Protocol replay and ledger parity checks for controller-child runs.
5. CI conformance gate for controller contracts and integration tests.
6. Bootstrap template for externalized `controller_workload` extension.
7. External install-path migration plan and guidance.
8. Environment rollout controls and feature flags for enablement.
9. Live end-to-end verification using external install path.
10. Reliability hardening cycle for failure taxonomy and flake boundaries.
11. v1 planning handoff packet for bounded parallel + broader child-type support.

## 3. Workstreams

### Workstream A - Operations and Guidance

Deliver:
1. Operator runbook for controller lifecycle and troubleshooting.
2. Authoring guide for controller extension usage and policy caps.
3. Migration guidance from in-repo bootstrap to external install path.

Acceptance:
1. Runbook is explicit on primary/fallback/blocked execution paths.
2. Migration guidance references canonical install/runtime authority paths.

### Workstream B - Runtime Hardening

Deliver:
1. Recursion/cycle rule hardening where ambiguity remains.
2. Error normalization hardening for child failures.
3. Deterministic provenance/summarization regression safeguards.

Acceptance:
1. No regression to v1 stable error codes.
2. Deterministic canonical summary serialization remains stable.

### Workstream C - Observability and Verification Surfaces

Deliver:
1. Controller-run metrics/events with deterministic field contracts.
2. Replay/parity checks for controller-child runs.
3. CI conformance gate for controller contract and integration coverage.

Acceptance:
1. CI gate fails closed on contract/integration regressions.
2. Replay/parity artifacts are reproducible for equivalent inputs.

### Workstream D - Externalization and Rollout

Deliver:
1. External extension template for `controller_workload`.
2. Environment rollout controls/feature flags.
3. Live external-install-path verification evidence.

Acceptance:
1. External install path executes via standard extension runtime route.
2. In-repo bootstrap remains non-privileged and migration-safe.

## 4. Verification Plan

Test and proof expectations:
1. Contract tests for any new/changed schema or serialization contracts.
2. Unit tests for hardening logic and guard transitions.
3. Integration tests through authoritative runtime paths.
4. Live verification for external install-path integration behavior.

Evidence outputs:
1. Path classification: `primary`, `fallback`, `degraded`, or `blocked`.
2. Result classification: `success`, `failure`, `partial_success`, or `environment_blocker`.
3. Exact failing step + exact error when blocked.

## 5. Completion Gate

Phase 2 is complete when:
1. Workstreams A-D acceptance criteria are met.
2. CI conformance gate is present and enforcing controller checks.
3. External install-path live verification evidence is recorded.
4. Rollout controls are documented and test-covered.
5. v1 planning handoff packet is published for the next phase.
