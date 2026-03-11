# Orket Truthful Runtime Hardening Phase D Implementation Plan

Last updated: 2026-03-10
Status: Staged / Waiting (proof not yet established)
Owner: Orket Core
Canonical lane plan: `docs/projects/future/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
Depends on: Phase C completion

## 1. Objective

Make memory mutation and trust semantics explicit so the system does not mutate or rely on context without policy truth.

## 2. Scope Deliverables

1. Session memory policy contract (working memory, durable memory, reference context).
2. Memory write threshold contract (criteria + rationale requirements).
3. Memory conflict resolution contract (contradiction/staleness/user correction).
4. Tool result trust-level contract (`authoritative`, `advisory`, `stale_risk`, `unverified`).

## 3. Detailed Workstreams

### Workstream D1 - Memory Policy Surfaces
Tasks:
1. Define allowed read/write paths for each memory class.
2. Define write-threshold policy for when memory mutation is allowed.
3. Require rationale capture for writes in governed lanes.

Acceptance:
1. memory writes are no longer implicit side effects.
2. memory reads/writes are class-aware and policy-constrained.

### Workstream D2 - Conflict and Correction Handling
Tasks:
1. Define contradiction detection and resolution rules.
2. Define staleness handling and correction precedence for user updates.
3. Specify correction observability events and reconciliation states.

Acceptance:
1. conflict behavior is deterministic and auditable.
2. user correction has explicit priority semantics.

### Workstream D3 - Trust Levels in Synthesis
Tasks:
1. Apply trust-level classification to tool outputs.
2. Define synthesis constraints for low-trust inputs.
3. Ensure truth classification reflects trust-level impact.

Acceptance:
1. synthesis behavior is explicitly gated by trust level in governed lanes.
2. trust semantics are user-visible where required.

## 4. Verification Plan

1. Contract tests for memory class rules, write thresholds, and conflict resolution states.
2. Integration tests for correction and reconciliation behavior.
3. End-to-end tests for trust-level impact on final synthesis.

## 5. Completion Gate

Phase D is complete when:
1. memory write/read behavior is policy-bound and auditable,
2. conflict/correction behavior is deterministic and test-backed,
3. tool trust levels affect synthesis as specified.
