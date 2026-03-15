# Orket Truthful Runtime Hardening Phase C Implementation Plan

Last updated: 2026-03-15
Status: Staged after completion of packet-1 cleanup and packet-2 slices 1-2; remaining Phase C backlog staged
Owner: Orket Core
Canonical lane plan: `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
Depends on: Phase B completion
Accepted packet-1 requirements archive: `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/TRH03142026-PHASE-C-REQUIREMENTS.md`
Archived packet-1 authority:
1. `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/TRH03142026-PHASE-C-IMPLEMENTATION-PLAN.md`
2. `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/TRH03142026-PHASE-C-REQUIREMENTS.md`
3. `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/CLOSEOUT.md`
Frozen cycle-1 closeout:
1. `docs/projects/archive/truthful-runtime/TRH03142026-PHASE-C-CYCLE1/CLOSURE-MATRIX.md`
2. `docs/projects/archive/truthful-runtime/TRH03142026-PHASE-C-CYCLE1/CLOSEOUT.md`
3. `benchmarks/staging/General/truthful_runtime_phase_c_cycle1_live_closure_qwen2_5_coder_7b_2026-03-14.json`
Archived cleanup packet:
1. `docs/projects/archive/truthful-runtime/TRH03152026-PACKET1-CLEANUP/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-C-PACKET1-CLEANUP-IMPLEMENTATION-PLAN.md`
Next staged packet:
1. `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-C-PACKET2-IMPLEMENTATION-PLAN.md`
Completed bounded packet-2 slice contracts:
1. `docs/specs/TRUTHFUL_RUNTIME_REPAIR_LEDGER_CONTRACT.md`
2. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`

## 0. Current Role

This file is not the active authority for implementation details of the bounded first Phase C packet, the archived packet-1 cleanup packet, or future packet-2 slices.

Accepted packet-1 requirements now live in:
1. `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/TRH03142026-PHASE-C-REQUIREMENTS.md`
Packet-1 implementation and closeout now live in:
1. `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/TRH03142026-PHASE-C-IMPLEMENTATION-PLAN.md`
2. `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/CLOSEOUT.md`

This file now governs the phase-level boundary while the packet-1 cleanup packet is archived and the remaining packet-2 backlog stays staged. It must not be treated as authorization to reopen packet-2 work without an explicit next-slice request.

The live-proof closure boundary remains frozen in the cycle-1 archive. Repair-ledger and artifact-provenance slices are complete; the archived cleanup packet realigns packet-1 semantics and supersedes the affected live proofs; the remaining Phase C backlog stays staged.

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
2. Define structured repair ledger entries and final disposition rules. Status: Completed in packet-2 slice 1.
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
4. Define artifact generation provenance envelope. Status: Completed in packet-2 slice 2.

Acceptance:
1. high-stakes mode blocks synthesis without required evidence path.
2. voice/artifact truth surfaces are distinct and non-misleading.

## 4. Verification Plan

1. Contract tests for provenance envelope, repair ledger, truth classification, and idempotency keys.
2. Integration tests for cancellation truth, fallback detection, repair-ledger reconstruction, and audit behavior.
3. End-to-end tests validating repaired-path behavior and narration/effect alignment in user-visible flows.

## 5. Completion Gate

Phase C is complete when:
1. provenance/repair/fallback/truth semantics are emitted per run,
2. silent fallback and narration/effect mismatches are detectable,
3. high-stakes evidence/source contracts are testable and enforced.
