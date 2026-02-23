Engineering Execution Doctrine (OS v1)

Status: Normative
Applies To: All work under docs/projects/OS/ and orket/kernel/v1/
Version: os/v1

Purpose

This document defines how Orket OS v1 is engineered.

It prevents:

Architectural drift

Overlapping subsystem rewrites

Silent contract breakage

“Almost deterministic” implementations

Feature-first entropy

It enforces:
Constitution-first, slice implementation.

1. Design Philosophy

We do not design the entire OS before writing code.

We do fully design the constitutional surfaces before implementation.

The rule:

Lock invariants.
Defer features.

2. What Must Be Locked Before Implementation

The following are constitutional and MUST be finalized before implementation proceeds.

2.1 Contract Boundaries

Kernel ↔ Host boundary

DTO schemas (JSON Schema in contracts/)

Versioning rules

Error code registry

AdditionalProperties policy

No code may precede stable contract definitions.

2.2 State & Persistence Model

The following MUST be fully defined:

LSI disk anatomy

Staging vs committed separation

Shadowing order:
Self → Staging → Committed

Stem-scoped pruning law

Deletion semantics (Option A)

Atomic promotion pattern

Deterministic ordering rules

If storage rules are vague, implementation is prohibited.

2.3 Determinism Physics

Must be frozen:

Canonical JSON rules

Structural digest computation

Sorting rules

RFC6901 pointer discipline

Narrative vs Canonical boundary

If identity changes, everything changes.

Therefore identity is constitutional.

3. What May Be Implemented Incrementally

The following may evolve behind stable contracts:

Scheduler internals

Replay engine internals

Capability policy expression language

Plugin ecosystem breadth

Future mesh/distributed layer

UI/runtime integration

These must not alter:

On-disk format

DTO shapes

Deterministic rules

Promotion semantics

4. Implementation Strategy
Phase 0 — Constitution Lock

Complete:

Contract schemas

Spec-002 (LSI)

Spec-003 (TurnResult)

Versioning policy

Test policy

Contract index

Error code registry

No feature work begins before this phase completes.

Phase 1 — Minimal Executable Slice

Implement only:

canonical utilities

contracts module

LSI core (shadowing + integrity)

Promotion atomicity

Minimal execute_turn

The first goal is:

A PASS/FAIL TurnResult that obeys all laws.

Not a feature-complete runtime.

Phase 2 — Expand Behind Interfaces

Add:

Replay engine

Capability enforcement

Run lifecycle strict sequencing

These must pass existing constitutional tests without modification.

5. The Overlap Rule

If a change affects:

On-disk layout

Structural digest logic

DTO schema

Error code meaning

Stage ordering

Promotion atomicity

Then:

It requires constitutional review
It requires version policy evaluation
It may require major version bump

6. Fail-Closed Engineering

Orket OS v1 is fail-closed by default.

If:

Diff context missing

Link target missing

Capability undecided

Version unknown

Canonicalization ambiguous

The kernel MUST fail deterministically.

No silent recovery.

7. PR Acceptance Doctrine

A PR is rejected if:

It modifies a normative schema without version bump

It changes deterministic ordering

It alters canonicalization rules

It introduces partial promotion behavior

It removes or renames error codes

It makes committed/ writable during execute_turn

Tests are constitutional enforcement.

8. Narrative vs State Discipline

State Stream:

Canonical JSON

Structural digest

Persisted

Compared

Narrative Stream:

Deterministic single-line events

Not digested

Not part of identity

Never digest logs.

9. The Golden Rule

If a decision would force rewriting LSI, changing digests, or modifying DTO shapes:

Stop.

Update constitution first.
Version appropriately.
Then implement.

10. Definition of Done (OS v1)

OS v1 is complete when:

All contracts are versioned and validated

All constitutional laws have scenario tests

Replay is stable

Promotion is atomic

Capability enforcement is deterministic

No drift between docs and schemas

Final Principle

Orket OS is not built by feature velocity.
It is built by invariant stability.

Lock invariants.
Slice implementation.
Expand behind contracts.