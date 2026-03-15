# Orket Truthful Runtime Hardening Phase C Implementation Plan

Last updated: 2026-03-14
Status: Staged / Waiting (broader Phase C backlog beyond active packet-1 plan)
Owner: Orket Core
Canonical lane plan: `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
Depends on: Phase B completion
Accepted requirements lane: `docs/projects/truthful-runtime/TRH03142026-PHASE-C-REQUIREMENTS.md`
Active packet-1 implementation plan: `docs/projects/truthful-runtime/TRH03142026-PHASE-C-IMPLEMENTATION-PLAN.md`

## 0. Current Role

This file is no longer the active authority for the bounded first Phase C packet.

Accepted packet-1 requirements now live in:
1. `docs/projects/truthful-runtime/TRH03142026-PHASE-C-REQUIREMENTS.md`
Active packet-1 implementation now lives in:
1. `docs/projects/truthful-runtime/TRH03142026-PHASE-C-IMPLEMENTATION-PLAN.md`

This file remains staged continuation input only for broader Phase C backlog beyond packet-1 and must not be treated as authorization to widen the active packet-1 implementation scope.

## 1. Objective

Make execution provenance, repair behavior, fallback behavior, and truth classification first-class runtime outputs.

## 2. Scope Deliverables

1. Execution provenance envelope contract.
2. Structured repair ledger contract.
3. Response truth classification contract.
4. Narration-to-effect audit contract.
5. Silent fallback detector contract.
6. Cancellation truth path contract.
7. Idempotency key policy for retries/writes/events/repairs.
8. Source attribution and evidence-first mode contracts.
9. Voice truth contract.
10. Artifact generation provenance contract.

## 3. Detailed Workstreams

### Workstream C1 - Provenance and Repair Surfaces
Tasks:
1. Define/enforce provenance envelope fields (provider/model/profile/tool/retry/repair/fallback).
2. Define structured repair ledger entries and final disposition rules.
3. Link retry/repair/fallback events with stable idempotency keys.

Acceptance:
1. every run emits provenance with attributable repair/fallback history.
2. repeated delivery paths remain idempotency-safe.

### Workstream C2 - Truth and Audit Semantics
Tasks:
1. Implement response truth classification states.
2. Implement narration-to-effect audit checks and failure reason capture.
3. Introduce silent fallback defect classification and observability routing.

Acceptance:
1. user-visible narration maps to real effects or explicit non-effect reasons.
2. unannounced fallback is detectable and reportable as a defect class.

### Workstream C3 - High-Stakes Evidence and Voice Truth
Tasks:
1. Define evidence-first synthesis requirements for high-stakes lanes.
2. Define source attribution contract (cited facts vs uncited reasoning).
3. Define voice truth separation (text completion, TTS generation, playback, lip-sync).
4. Define artifact generation provenance envelope.

Acceptance:
1. high-stakes mode blocks synthesis without required evidence path.
2. voice/artifact truth surfaces are distinct and non-misleading.

## 4. Verification Plan

1. Contract tests for provenance envelope, repair ledger, truth classification, and idempotency keys.
2. Integration tests for cancellation truth, fallback detection, and audit behavior.
3. End-to-end tests validating narration/effect alignment in user-visible flows.

## 5. Completion Gate

Phase C is complete when:
1. provenance/repair/fallback/truth semantics are emitted per run,
2. silent fallback and narration/effect mismatches are detectable,
3. high-stakes evidence/source contracts are testable and enforced.
