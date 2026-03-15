# Orket Truthful Runtime Hardening Phase C Packet-1 Cleanup Implementation Plan

Last updated: 2026-03-15
Status: Completed
Owner: Orket Core
Parent lane authority: `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
Closeout:
1. `docs/projects/archive/truthful-runtime/TRH03152026-PACKET1-CLEANUP/CLOSEOUT.md`
Frozen baseline:
1. `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/CLOSEOUT.md`
2. `benchmarks/staging/General/truthful_runtime_packet1_live_proof_qwen2_5_coder_7b_2026-03-14.json`
3. `benchmarks/staging/General/truthful_runtime_packet2_repair_live_proof_qwen2_5_coder_7b_2026-03-14.json`
Contract delta:
1. `docs/architecture/CONTRACT_DELTA_TRUTHFUL_RUNTIME_PACKET1_BOUNDARY_REALIGNMENT_2026-03-15.md`

## Objective

Realign packet-1 to classify the operator-facing primary work boundary instead of defaulting to the runtime-owned verification artifact, tighten required intended-path provenance values, and supersede the affected live proof artifacts under the corrected contract.

## Scope

In scope:
1. packet-1 primary-output boundary selection narrowing
2. stable missing-token handling for required intended-path provenance fields
3. contract tests freezing `classification_basis.rule -> evidence_source`
4. packet-1 and packet-2 repair live-proof supersession under the corrected packet-1 boundary

Out of scope:
1. new packet-2 backlog slices
2. narration-to-effect audit
3. source attribution and evidence-first mode
4. organic path-mismatch or silent-unrecorded-fallback live proof
5. avatar/lipsync work

## Deliverables

1. Updated packet-1 contract in `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
2. Runtime implementation updates in `orket/runtime/run_summary.py` and `orket/runtime/execution_pipeline.py`
3. Contract and integration test updates covering boundary order, missing-token semantics, and `classification_basis` mapping
4. Canonical packet-1 live recorder script and rerunnable result artifact
5. Superseding staged packet-1 and packet-2 repair live proof candidates plus updated staging index/README

## Boundary Rule

Packet-1 primary-output selection order for this cleanup packet is:
1. explicit completion output
2. explicitly designated work artifact
3. direct response output
4. runtime verification artifact fallback
5. none

Runtime verification is a truthful fallback boundary only when no stronger operator-facing boundary was designated.

## Provenance Rule

Required intended-path provenance fields must not emit implementation placeholders such as `"None"` or `"unknown"` for missing intended data.

This packet introduces one stable contract token for absent intended-path data:
1. `missing`

## Exit Artifacts

1. `benchmarks/results/governance/truthful_runtime_packet1_live_proof.json`
2. `benchmarks/staging/General/truthful_runtime_packet1_boundary_cleanup_live_proof_qwen2_5_coder_7b_2026-03-15.json`
3. `benchmarks/staging/General/truthful_runtime_packet2_repair_live_proof_qwen2_5_coder_7b_2026-03-15.json`

## Verification

Required:
1. contract tests for boundary order and `classification_basis` mapping
2. integration tests for packet-1 selection and intended-path missing-token behavior
3. provider-backed live packet-1 proof rerun on the corrected boundary
4. provider-backed live packet-2 repair proof rerun on the corrected boundary

Observed path/result labels must be recorded in the superseding proof artifacts.
