# Controller Workload Phase 2C Implementation Plan

Last updated: 2026-03-08
Status: Active
Owner: Orket Core
Source requirements: `docs/projects/controller-workload/04-REQUIREMENTS-Phase-2C.md`
Runtime contract authority: `docs/specs/CONTROLLER_WORKLOAD_V1.md`
Observability contract authority: `docs/specs/CONTROLLER_OBSERVABILITY_V1.md`

## 1. Objective

Implement Phase 2C exactly as defined in `04-REQUIREMENTS-Phase-2C.md` for initiative steps 17-20:
1. external install migration path for controller extension
2. migration guidance publication for bootstrap-to-external transition
3. rollout controls for controller enablement
4. live external install-path verification

## 2. Scope Deliverables

### 2.1 External Install Migration Utility
1. utility path to materialize an external-style controller extension repository from template assets
2. integration path to install and execute controller workload from that repository

### 2.2 Verification Coverage
1. integration test proving install-path migration behavior through `ExtensionManager.run_workload`
2. parity/behavior assertions for runtime contract stability

### 2.3 Migration Guidance
1. migration guide updates with executable command flow and verification steps

### 2.4 Rollout Controls
1. environment-based controller enablement controls
2. stable blocked behavior for policy-disabled runs

### 2.5 Live External Verification Evidence
1. recorded integration verification through installed external-style controller repo path
2. path/result classification and error-step evidence where applicable

## 3. Workstream Plan

### Workstream A - Install Migration Path (Step 17)
Tasks:
1. add migration utility path for external-style repo bootstrap
2. verify installation and run path via integration tests

Acceptance:
1. controller workload executes from installed external-style repo path
2. no alternate dispatch path is introduced

### Workstream B - Migration Guidance (Step 18)
Tasks:
1. update guidance with migration command sequence and validations
2. capture blockers/fallback notes where external infrastructure is unavailable

Acceptance:
1. guide is command-accurate and contract-aligned

### Workstream C - Rollout Controls + Live Verification (Steps 19-20)
Tasks:
1. add environment rollout controls for controller enablement
2. verify blocked behavior and observability consistency under disablement
3. run external-style install-path integration verification and record evidence

Acceptance:
1. policy-disabled runs return blocked with stable error code
2. external-style install-path integration run is verified end-to-end

## 4. Implementation Order

1. migration utility implementation
2. integration test proof
3. migration guide update
4. rollout controls and verification evidence

## 5. Completion Gate

Phase 2C is complete when:
1. migration utility and integration proof are in place
2. guidance is published and aligned with runtime authority
3. rollout controls are implemented and verified
4. live external install-path verification evidence is recorded
