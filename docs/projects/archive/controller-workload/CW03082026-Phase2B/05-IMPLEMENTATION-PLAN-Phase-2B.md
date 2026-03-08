# Controller Workload Phase 2B Implementation Plan

Last updated: 2026-03-08
Status: Active
Owner: Orket Core
Source requirements: `docs/projects/controller-workload/04-REQUIREMENTS-Phase-2B.md`
Runtime contract authority: `docs/specs/CONTROLLER_WORKLOAD_V1.md`
Observability contract authority: `docs/specs/CONTROLLER_OBSERVABILITY_V1.md`

## 1. Objective

Implement Phase 2B exactly as defined in `04-REQUIREMENTS-Phase-2B.md` for initiative steps 14-16:
1. controller replay/parity checks
2. controller CI conformance gate
3. externalization bootstrap template

## 2. Scope Deliverables

### 2.1 Replay/Parity Runtime Surface
1. controller parity comparator module for run summary and observability projection
2. deterministic mismatch reporting and parity digest output

### 2.2 Scriptable Parity Command
1. script entrypoint for comparing two controller run artifacts
2. strict mode to fail on mismatch
3. diff-ledger-compliant output when writing JSON files

### 2.3 CI Conformance Gate
1. `.gitea` workflow updates enforcing controller checks
2. fail-closed behavior on parity/test regressions

### 2.4 Externalization Bootstrap Template
1. template scaffold for external controller extension packaging
2. migration notes preserving standard extension runtime authority

## 3. Workstream Plan

### Workstream A - Replay/Parity Implementation (Step 14)
Tasks:
1. add controller parity comparator runtime module
2. define deterministic normalization and mismatch surfaces
3. add contract/unit/integration tests for parity behaviors

Acceptance:
1. equivalent runs pass parity deterministically
2. semantic drifts fail parity with concrete mismatch details

### Workstream B - CI Conformance Gate (Step 15)
Tasks:
1. update `.gitea` workflow lane for controller checks
2. include controller parity checks in gate command set

Acceptance:
1. workflow fails closed when controller checks fail

### Workstream C - Externalization Template (Step 16)
Tasks:
1. add bootstrap template and migration notes for external repo path
2. ensure no privileged runtime route is introduced

Acceptance:
1. template is migration-ready and references canonical runtime/install authority

## 4. Implementation Order

1. replay/parity runtime and tests
2. parity script path
3. CI gate updates
4. externalization template and migration notes

## 5. Completion Gate

Phase 2B is complete when:
1. replay/parity runtime and script paths are present and tested
2. controller CI gate updates are active and fail closed
3. externalization bootstrap template + guidance are published
