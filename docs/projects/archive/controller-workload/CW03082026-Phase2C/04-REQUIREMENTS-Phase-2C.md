# Controller Workload Phase 2C Requirements (External Install Migration + Rollout Controls + Live Verification)

Last updated: 2026-03-08
Status: Accepted
Owner: Orket Core
Initiative authority: `docs/projects/archive/controller-workload/CW03082026-Initiative-Closeout/02-INITIATIVE-MINI-ROADMAP.md`
Runtime contract authority: `docs/specs/CONTROLLER_WORKLOAD_V1.md`
Observability contract authority: `docs/specs/CONTROLLER_OBSERVABILITY_V1.md`

## 1. Purpose

Define the next bounded requirement slice after Phase 2B closeout.

Phase 2C covers initiative steps 17-20:
1. migrate controller extension execution to external install-path usage
2. publish migration guidance from in-repo bootstrap to external extension install path
3. add environment rollout controls/feature flags for controller enablement
4. run live end-to-end integration verification with external install path

## 2. Scope

In scope:
1. executable migration path that installs controller extension from an external-style repository layout
2. integration proof that controller runtime behavior remains contract-aligned after install-path migration
3. migration guide updates using the implemented path

Out of scope:
1. reliability hardening cycle and v1-next planning (steps 21-22)

## 3. Non-Negotiable Invariants

1. Child dispatch authority remains `ExtensionManager.run_workload`.
2. No privileged alternate execution path is introduced.
3. Stable controller error codes and run-result invariants remain unchanged.
4. Observability fail-closed behavior remains mandatory.

## 4. Requirements

### 4.1 External Install Migration Path

Requirements:
1. provide a migration utility path that materializes/install-tests an external-style controller extension repo
2. preserve canonical runtime behavior through installed extension execution
3. keep in-repo bootstrap non-authoritative once migration path is active

Acceptance:
1. integration run through installed external-style repo succeeds
2. parity checks against existing behavior remain green for equivalent payloads

### 4.2 Migration Guidance

Requirements:
1. publish concrete migration steps, prerequisites, and validation commands
2. identify fallback behavior and known blockers clearly

Acceptance:
1. guide maps directly to executable commands
2. guide references canonical authority docs/specs

### 4.3 Rollout Controls

Requirements:
1. add environment-based enablement controls for controller workload execution
2. disabled runs must fail closed with stable blocked semantics

Acceptance:
1. policy-disabled runs return blocked result with stable error surface
2. observability behavior remains deterministic and contract-aligned when disabled

### 4.4 Live External Install Verification

Requirements:
1. execute a real end-to-end controller run through an installed external-style repository path
2. capture path/result outcome and failing-step detail when failures occur

Acceptance:
1. integration verification runs through `ExtensionManager.run_workload` with installed external-style repo path
2. verification evidence includes observed path/result classification

## 5. Verification Requirements

Required test layers:
1. unit
2. integration

Minimum expectations:
1. integration test installs controller extension from external-style repo path and executes through `ExtensionManager.run_workload`
2. parity or behavior assertions confirm no contract drift
3. rollout-control integration tests validate blocked behavior and stable error code mapping

## 6. Completion Criteria

Phase 2C requirements are satisfied when:
1. external install migration path exists and is test-covered
2. migration guidance is published and command-valid
3. rollout controls are implemented and test-covered
4. live external install verification evidence is recorded
5. targeted tests pass for changed paths

## 7. Implementation Pointer

Accepted implementation plan for this slice:
1. `docs/projects/controller-workload/05-IMPLEMENTATION-PLAN-Phase-2C.md`
