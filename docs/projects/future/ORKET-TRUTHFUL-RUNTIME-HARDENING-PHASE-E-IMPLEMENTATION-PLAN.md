# Orket Truthful Runtime Hardening Phase E Implementation Plan

Last updated: 2026-03-10
Status: Staged / Waiting (proof not yet established)
Owner: Orket Core
Canonical lane plan: `docs/projects/future/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
Depends on: Phase D completion

## 1. Objective

Operationalize conformance and promotion discipline so releases are evidence-backed and user-truth aligned.

## 2. Scope Deliverables

1. Behavioral contract test suite.
2. False-green test hunt checklist/process.
3. Golden transcript suite with diffing rules.
4. User expectation alignment test suite.
5. Operator sign-off artifact contract.
6. Promotion gates by evidence contract.
7. Operational scorecard contract.
8. Repo introspection mode report shape.
9. Spec debt backlog structure.
10. Canonical philosophy document.
11. UI degradation language standards.
12. Workspace hygiene rules.
13. Cross-spec consistency checker scope and policy.

## 3. Detailed Workstreams

### Workstream E1 - Conformance Test and Transcript Governance
Tasks:
1. Define behavioral contract test matrix by user-visible claims.
2. Define false-green detection checklist and standing cadence.
3. Define golden transcript corpus, storage, and diff policy.

Acceptance:
1. runtime truth checks cannot be replaced by helper-only assertions.
2. transcript diffs surface meaningful behavioral drift.

### Workstream E2 - Promotion and Operator Governance
Tasks:
1. Define operator sign-off bundle shape (logs/transcripts/metrics/failures/decision notes).
2. Define evidence thresholds for profile/provider promotion.
3. Define regression quarantine trigger thresholds.
4. Define release operational scorecard dimensions.

Acceptance:
1. promotion requires repeated passing evidence.
2. failing conformance profiles are auto-downgradable by policy.

### Workstream E3 - Ecosystem Hygiene and Trust Language
Tasks:
1. Define spec debt backlog format and ownership.
2. Define cross-spec consistency checker and failure policy.
3. Define standardized UI degradation language.
4. Define workspace hygiene rules and repo introspection report format.
5. Publish short canonical philosophy document.

Acceptance:
1. contract drift becomes machine-detectable debt.
2. user-facing labels match runtime truth.
3. philosophy and hygiene constraints are explicit and enforceable.

## 4. Verification Plan

1. End-to-end behavioral test runs with transcript diff evidence.
2. Promotion-gate dry runs using sign-off artifact bundles.
3. Consistency-check runs validating vocabulary/contract alignment across docs/schemas/tests/runtime.
4. Expectation-alignment checks for `saved`, `synced`, `used memory`, `searched`, and `verified`.

## 5. Completion Gate

Phase E is complete when:
1. promotion path is evidence-gated and operator-auditable,
2. behavioral and expectation-alignment tests are active and enforced,
3. drift-detection and spec-debt handling are operational.
