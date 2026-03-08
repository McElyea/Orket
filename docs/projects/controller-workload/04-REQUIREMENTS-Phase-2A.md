# Controller Workload Phase 2A Requirements (Operations + Runtime Hardening + Observability)

Last updated: 2026-03-08
Status: Accepted
Owner: Orket Core
Initiative authority: `docs/projects/controller-workload/02-INITIATIVE-MINI-ROADMAP.md`
Runtime contract authority: `docs/specs/CONTROLLER_WORKLOAD_V1.md`
Observability contract authority: `docs/specs/CONTROLLER_OBSERVABILITY_V1.md`

## 1. Purpose

Define the next right-sized requirement slice after Phase 1 closeout.

Phase 2A covers initiative steps 11-13 only:
1. operator authoring and runtime runbook docs
2. recursion/cycle and error-schema hardening
3. observability metrics/events for controller runs

This slice intentionally excludes externalization, rollout controls, and live external install-path verification.

## 2. Scope

In scope:
1. Operator runbook for controller execution paths, failure modes, and troubleshooting.
2. Authoring guidance for controller workload usage and policy-cap semantics.
3. Runtime hardening for recursion/cycle normalization where ambiguity remains.
4. Error normalization contract hardening for child failure surfaces.
5. Deterministic observability contract for controller-run metrics/events.
6. Tests and evidence for the above changes.

Out of scope (deferred to later slices):
1. Replay/parity framework expansion.
2. CI conformance gate implementation.
3. Externalized extension template and migration execution.
4. Feature flags and rollout controls.
5. Live external install-path verification.

## 3. Non-Negotiable Carry-Forward Invariants

Phase 2A must preserve these existing truths:
1. Child execution remains sequential.
2. Child dispatch authority remains `ExtensionManager.run_workload`.
3. Fail-closed runtime behavior remains mandatory.
4. Stable controller error codes remain authoritative.
5. Deterministic provenance and canonical summary behavior remain mandatory.

## 4. Requirements

### 4.1 Operator Runbook and Authoring Guide

Required artifacts:
1. Controller operator runbook with path classification:
   - `primary`
   - `fallback`
   - `degraded`
   - `blocked`
2. Controller authoring guide with explicit cap-request semantics and denial behavior.

Required runbook coverage:
1. envelope validation failure path
2. sdk-child denial path
3. depth/fanout cap denial paths
4. recursion/cycle denial paths
5. child failure path under stop-on-first-failure
6. expected artifact/provenance surfaces for successful and failed runs

Acceptance:
1. Operators can classify observed behavior without inspecting implementation internals.
2. Authoring guidance matches current runtime truth and stable error-code contract.

### 4.2 Runtime Hardening (Recursion/Cycle/Error)

Requirements:
1. Recursion and cycle detection behavior must be unambiguous at runtime and documentation levels.
2. Error normalization must produce stable, deterministic error envelopes for child failure outcomes.
3. Runtime must not introduce alternate dispatch paths or direct child entrypoint invocation.

Acceptance:
1. Existing stable error codes remain unchanged.
2. Regression tests confirm no behavioral drift in deterministic ordering or stop-on-first-failure behavior.

### 4.3 Observability Contract for Controller Runs

Requirements:
1. Define deterministic event/metric fields for each controller run and each child result.
2. Observability fields must include enough context to correlate:
   - requested caps
   - enforced caps
   - denial/failure code
   - child execution order index
3. Observability output ordering must match execution ordering.
4. Machine-readable schema artifact must exist at `schemas/controller_observability_v1.json` and match the contract.

Acceptance:
1. Equivalent inputs produce equivalent ordered observability payloads.
2. Observability contract is documented in a durable spec path before implementation is finalized.

## 5. Test and Verification Requirements

Required test layers:
1. contract
2. unit
3. integration

Minimum verification expectations:
1. Contract tests for any new/changed observability schema and error-normalization envelope.
2. Unit tests for recursion/cycle guard hardening and normalization edge cases.
3. Integration tests through `ExtensionManager.run_workload` for denial/failure observability capture.

Evidence requirements:
1. Report observed execution path (`primary`, `fallback`, `degraded`, `blocked`).
2. Report observed result (`success`, `failure`, `partial_success`, `environment_blocker`).
3. If blocked/failure, capture exact failing step and exact error.

## 6. Completion Criteria

Phase 2A requirements are satisfied when:
1. Runbook and authoring guidance are published and aligned with runtime truth.
2. Recursion/cycle/error hardening is implemented without altering stable error-code identities.
3. Deterministic observability contract is documented and implemented.
4. `schemas/controller_observability_v1.json` exists and contract tests validate payloads against it.
5. Contract/unit/integration tests pass for changed behavior.
6. Evidence report is recorded with explicit path/result classification.

## 7. Traceability to Initiative Mini-Roadmap

1. Step 11 -> Section 4.1
2. Step 12 -> Section 4.2
3. Step 13 -> Section 4.3

## 8. Next Planning Boundary

After Phase 2A completion, create the next requirements slice for steps 14-16 (replay/parity + CI gate + externalization template) as a separate, explicitly named requirements document.

## 9. Implementation Pointer

Accepted implementation plan for this slice:
1. `docs/projects/controller-workload/05-IMPLEMENTATION-PLAN-Phase-2A.md`
