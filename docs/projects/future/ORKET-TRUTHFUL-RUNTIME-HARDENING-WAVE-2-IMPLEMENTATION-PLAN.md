# Orket Truthful Runtime Hardening Wave 2 Implementation Plan

Last updated: 2026-03-10
Status: Active (in progress)
Owner: Orket Core
Canonical lane plan: `docs/projects/future/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
Purpose: convert second-wave hardening backlog into executable slices with explicit acceptance gates.

## 1. Objective

Operationalize additional truth and governance controls so runtime claims remain attributable under stress, retries, drift, and promotion pressure.

## 1A. Progress Snapshot (2026-03-10)

Completed in active execution:
1. contract drift checker, trace IDs, acceptance gate runner seed
2. unknown-input policy, provider quarantine controls, result-error invariants
3. clock/time authority policy, capability fallback hierarchy, safe default catalog
4. runtime truth dashboard seed metrics and test taxonomy enforcement
5. unreachable-branch detector, no-op critical-path detector, environment parity checklist
6. state transition Mermaid exporter, cross-lane dependency map generator, structured warning policy checks
7. model profile BIOS contract, checker, run-start artifact, and acceptance-gate enforcement
8. interrupt semantics policy contract, checker, run-start artifact, and acceptance-gate enforcement
9. idempotency discipline policy contract, checker, run-start artifact, and acceptance-gate enforcement
10. strict artifact provenance block policy contract, checker, run-start artifact, and acceptance-gate enforcement
11. operator override logging policy contract, checker, run-start artifact, and acceptance-gate enforcement
12. demo-vs-production labeling policy contract, checker, run-start artifact, and acceptance-gate enforcement
13. human correction capture policy contract, checker, run-start artifact, and acceptance-gate enforcement
14. sampling discipline guide contract, checker, run-start artifact, and acceptance-gate enforcement
15. execution-readiness rubric contract, checker, run-start artifact, and acceptance-gate enforcement
16. release confidence scorecard contract, checker, run-start artifact, and acceptance-gate enforcement

## 2. Relationship to Existing Phase Plans

This Wave 2 plan extends (does not replace) existing phase plans A-E.

Execution preference:
1. land foundational prerequisites in Phase A/B/C first,
2. then execute Wave 2 slices in dependency order below.

## 3. Wave 2 Work Packets

## W2-A Contract and Authority Automation

Scope:
1. contract drift checker (docs/schemas/runtime enums/tests)
2. plan-to-code trace IDs
3. single-source status vocabulary
4. unknown-input policy
5. invariant registry
6. safe default catalog
7. config ownership map
8. cross-lane dependency map
9. state machine visualization export
10. clock/time authority policy
11. decision record template
12. Orket operating principles doc

Acceptance:
1. vocabulary/contract drift is machine-detectable.
2. requirements/acceptance items are traceable to tests and commits.
3. unknown-input and invariant behavior is canonical and shared.

## W2-B Runtime Control and Routing Resilience

Scope:
1. provider quarantine switch (no code edit required)
2. capability fallback hierarchy
3. retry classification (safe vs dangerous retries)
4. interrupt semantics policy (generalized beyond voice)
5. idempotency discipline beyond events (writes, asset loads, task execution, phase transitions)
6. result-to-error invariant checker
7. boundary audit checklist
8. naming discipline pass for mismatched identifiers

Acceptance:
1. flaky providers/profiles are quarantinable by policy.
2. downgrade/retry/interrupt behavior is explicit and testable.
3. status/result/error combinations are invariant-checked.

## W2-C Observability and Provenance Hardening

Scope:
1. strict artifact provenance block
2. runtime truth dashboard (fallback/repair/invalid payload/timeout/silent-degrade)
3. structured warning policy
4. observability redaction tests
5. sampling discipline guide
6. operator override logging
7. demo-vs-production labeling
8. human correction capture
9. trust language review

Acceptance:
1. warnings/events are machine-readable and classifiable.
2. dashboard metrics come from authoritative runtime artifacts.
3. overrides/demos/corrections are observable, attributable, and non-silent.

## W2-D Verification Infrastructure and Harnesses

Scope:
1. acceptance gate runner
2. failure replay harness
3. persistence corruption test suite
4. cold-start truth tests
5. long-session soak tests
6. resource pressure simulation lane
7. security boundary tests for UI lanes
8. test taxonomy enforcement (unit/contract/integration/live truth)
9. unreachable-branch detector
10. no-op detector for critical paths
11. environment parity checklist

Acceptance:
1. phase completion can be programmatically evaluated.
2. known-failure replay is reproducible with frozen inputs.
3. long-run and degraded-mode behavior is test-backed.

## W2-E Promotion and Execution Governance

Scope:
1. non-fatal error budget
2. promotion rollback criteria
3. interface freeze windows
4. evidence package generator
5. release confidence scorecard
6. execution-readiness rubric
7. feature-flag expiration policy
8. canonical examples library
9. spec debt queue
10. workspace hygiene rules

Acceptance:
1. promotion/rollback decisions are evidence-governed.
2. draft-to-execution readiness is rubric-based.
3. temporary controls (flags/examples/debt) are governed and expirable.

## 4. Sequencing and Dependencies

Recommended order:
1. W2-A
2. W2-B
3. W2-C
4. W2-D
5. W2-E

Critical path:
`W2-A -> W2-B -> W2-C -> W2-D -> W2-E`

## 5. Initial Executable Slice (Wave 2 T2)

Wave 2 T2 deliverables:
1. contract drift checker
2. plan-to-code trace ID contract
3. acceptance gate runner (minimum viable)
4. single-source status vocabulary freeze
5. unknown-input policy
6. provider quarantine switch (minimum viable)
7. runtime truth dashboard seed metrics

Exit criteria:
1. drift and phase-completion claims are machine-checkable.
2. provider quarantine and vocabulary truth are operational.
3. dashboard includes authoritative baseline rates for fallback/repair/timeouts/silent-degrade.

## 6. Verification Standards

1. Every Wave 2 packet must ship with:
   1. contract tests for new contract surfaces,
   2. integration tests for runtime truth behavior,
   3. at least one end-to-end or live-truth check where externally observable behavior changes.
2. Each test must declare taxonomy (`unit`, `contract`, `integration`, `live_truth`).
3. Gate runner output and evidence package output are required artifacts for packet closeout.

## 7. Risk Controls

1. Risk: process overhead without runtime value.
   1. Mitigation: each packet must show defect classes caught and prevented.
2. Risk: telemetry noise hides meaningful incidents.
   1. Mitigation: structured warning classes plus sampling discipline.
3. Risk: freeze windows block critical fixes.
   1. Mitigation: explicit emergency-break policy with override logging.
4. Risk: drift checker false positives.
   1. Mitigation: allowlisted exceptions with expiry and owner.

## 8. Coverage Map

| Backlog Item | Wave 2 Packet |
|---|---|
| Contract drift checker | W2-A |
| Plan-to-code trace IDs | W2-A |
| Acceptance gate runner | W2-D (T2 seed) |
| Runtime truth dashboard | W2-C (T2 seed) |
| Degradation-first UI standard | W2-C + W2-E |
| Single-source status vocabulary | W2-A |
| Unknown-input policy | W2-A |
| Invariant registry | W2-A |
| Boundary audit checklist | W2-B |
| Provider quarantine switch | W2-B (T2 seed) |
| Capability fallback hierarchy | W2-B |
| Strict artifact provenance block | W2-C |
| Human correction capture | W2-C |
| Decision record template | W2-A |
| Failure replay harness | W2-D |
| Non-fatal error budget | W2-E |
| Promotion rollback criteria | W2-E |
| Interface freeze windows | W2-E |
| Cross-lane dependency map | W2-A |
| State machine visualization export | W2-A |
| Persistence corruption test suite | W2-D |
| Cold-start truth tests | W2-D |
| Long-session soak tests | W2-D |
| Interrupt semantics policy | W2-B |
| Retry classification | W2-B |
| Safe default catalog | W2-A |
| Observability redaction tests | W2-C |
| Sampling discipline guide | W2-C |
| Idempotency discipline beyond events | W2-B |
| Clock/time authority policy | W2-A |
| Operator override logging | W2-C |
| Demo-vs-production labeling | W2-C |
| Evidence package generator | W2-E |
| Test taxonomy enforcement | W2-D |
| Naming discipline pass | W2-B |
| Spec debt queue | W2-E |
| Unreachable-branch detector | W2-D |
| No-op detector for critical paths | W2-D |
| Structured warning policy | W2-C |
| Result-to-error invariant checker | W2-B |
| Config ownership map | W2-A |
| Environment parity checklist | W2-D |
| Resource pressure simulation lane | W2-D |
| Security boundary tests for UI lanes | W2-D |
| Feature-flag expiration policy | W2-E |
| Canonical examples library | W2-E |
| Trust language review | W2-C |
| Execution-readiness rubric | W2-E |
| Release confidence scorecard | W2-E |
| Orket operating principles doc | W2-A |
