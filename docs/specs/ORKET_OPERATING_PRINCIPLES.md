# Orket Operating Principles

Last updated: 2026-03-10
Status: Active

## Purpose

This document defines the non-negotiable principles that govern Orket runtime behavior, verification, and promotion decisions.

These principles apply to:
1. runtime implementation choices,
2. governance checks and acceptance gates,
3. release and promotion evidence decisions.

## Principles

1. Truthful behavior before convenience.
   - Runtime claims must match observable behavior.
   - Unknown inputs must fail closed unless an explicit degradation contract exists.
2. Truthful verification before green theater.
   - Verification artifacts must prove the real behavior being claimed.
   - Structural checks are useful, but they are not substitutes for runtime truth.
3. Deterministic defaults over implicit heuristics.
   - Defaults must be explicit, documented, and discoverable in canonical contracts.
   - Retry, fallback, and routing behavior must be policy-bound.
4. Single authority per contract surface.
   - Runtime vocabulary, transition rules, and failure semantics must come from one canonical source each.
   - Drift between code/docs/tests is treated as a defect.
5. No silent fallback in critical paths.
   - Degraded or blocked behavior must be surfaced in machine-readable artifacts.
   - Operators must be able to explain what happened and why.
6. Evidence-gated promotion and rollback.
   - Promotion requires repeatable evidence, not single-run success.
   - Rollback criteria must be pre-declared and operationally measurable.

## Enforcement Signals

The following governance surfaces are expected to enforce these principles:
1. runtime truth contract drift checks,
2. runtime truth acceptance gate results,
3. invariants and unknown-input policy contracts,
4. no-op and unreachable-branch governance checks for critical paths.

## Non-Goals

This document does not define:
1. feature roadmap priorities,
2. contributor workflow mechanics,
3. UI-only style conventions.
