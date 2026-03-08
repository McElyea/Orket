# Controller Workload Phase 2B Requirements (Replay/Parity + CI Gate + Externalization Template)

Last updated: 2026-03-08
Status: Accepted
Owner: Orket Core
Initiative authority: `docs/projects/archive/controller-workload/CW03082026-Initiative-Closeout/02-INITIATIVE-MINI-ROADMAP.md`
Runtime contract authority: `docs/specs/CONTROLLER_WORKLOAD_V1.md`
Observability contract authority: `docs/specs/CONTROLLER_OBSERVABILITY_V1.md`

## 1. Purpose

Define the next bounded requirement slice after Phase 2A closeout.

Phase 2B covers initiative steps 14-16 only:
1. protocol replay and ledger parity checks for controller-child runs
2. CI conformance gate for controller contract/integration checks
3. bootstrap template for externalizing `extensions/controller_workload`

## 2. Scope

In scope:
1. Deterministic replay/parity comparison surface for controller outputs.
2. Scriptable parity check path suitable for local and CI execution.
3. CI gate workflow updates that fail closed on controller regressions.
4. Externalization bootstrap template structure and minimal migration-ready guidance.

Out of scope (deferred):
1. full external install-path migration execution
2. rollout controls and feature flags
3. live external install-path verification runbook

## 3. Non-Negotiable Carry-Forward Invariants

1. Child execution remains sequential.
2. Child dispatch authority remains `ExtensionManager.run_workload`.
3. Stable controller error codes remain authoritative.
4. Observability fail-closed behavior remains mandatory.
5. Deterministic canonical summary behavior remains mandatory.

## 4. Requirements

### 4.1 Controller Replay/Parity Surface

Requirements:
1. Implement a deterministic controller parity comparator for equivalent controller runs.
2. Comparison must include:
   - run-level summary invariants
   - ordered child execution semantics
   - observability projection parity (excluding `run_id` only)
3. Comparator output must be machine-readable and stable for equivalent inputs.
4. Comparator must classify parity outcome with explicit mismatch details.

Acceptance:
1. Equivalent run payloads produce parity success.
2. Semantic drift (status/error/order mismatch) produces parity failure with concrete mismatch fields.
3. Comparator behavior is covered by contract/unit tests.

### 4.2 Controller Ledger Parity Check Path

Requirements:
1. Provide a scriptable parity check command for controller replay artifacts.
2. Any rerunnable JSON output written by scripts must use diff-ledger conventions.
3. Parity output must be deterministic for equivalent inputs.

Acceptance:
1. Script supports strict fail-on-mismatch mode.
2. Script output remains stable and append-safe across reruns.

### 4.3 CI Conformance Gate

Requirements:
1. Add/extend `.gitea` CI workflow checks for controller contract/unit/integration coverage.
2. CI gate must fail closed when controller parity checks fail.
3. CI lane must execute only authoritative controller test targets for this slice.

Acceptance:
1. CI configuration references concrete controller tests/check commands.
2. Gate behavior is validated via workflow-targeted tests where practical.

### 4.4 Externalization Bootstrap Template

Requirements:
1. Provide a bootstrap template path for externalizing controller workload extension packaging.
2. Template must preserve standard runtime execution authority and avoid privileged dispatch.
3. Provide concise migration notes for extension authors.

Acceptance:
1. Template artifacts are usable as a starting point for external repo packaging.
2. Guidance references canonical install/runtime authority paths.

## 5. Test and Verification Requirements

Required test layers:
1. contract
2. unit
3. integration

Minimum expectations:
1. contract/unit tests for replay/parity comparator semantics
2. integration proof through `ExtensionManager.run_workload`-based controller runs feeding parity checks
3. script test coverage for strict mode and deterministic output behavior

## 6. Completion Criteria

Phase 2B requirements are satisfied when:
1. replay/parity comparison path exists and is test-covered
2. scriptable parity command path exists and passes targeted tests
3. CI conformance gate updates are present and fail closed on controller regressions
4. externalization bootstrap template exists with migration guidance

## 7. Implementation Pointer

Accepted implementation plan for this slice:
1. `docs/projects/controller-workload/05-IMPLEMENTATION-PLAN-Phase-2B.md`
