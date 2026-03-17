# TRH03142026 Phase C Packet-1 Implementation Plan

Last updated: 2026-03-14
Status: Archived
Owner: Orket Core
Accepted requirements: `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/TRH03142026-PHASE-C-REQUIREMENTS.md`
Durable contract: `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
Runtime-stability authority: `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
Related staged continuation:
1. `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
2. `docs/projects/archive/truthful-runtime/TRH03162026-PHASE-C-CLOSEOUT/CLOSEOUT.md`

## 0. Current Role

This file is the canonical active implementation plan for the bounded first truthful-runtime Phase C packet.

It governs only packet-1 implementation for:
1. execution provenance envelope
2. truth classification
3. silent fallback detection
4. packet-1 conformance

It does not authorize broader Phase C backlog items, Phase D, or Phase E work.

## 1. Objective

Implement the accepted packet-1 runtime truth surfaces so the runtime can:
1. emit machine-recorded execution provenance
2. emit deterministic truth classification for the selected primary output boundary when one exists
3. detect and report minimum silent fallback defects
4. preserve run-summary reconstruction compatibility
5. produce truthful proof artifacts for the new surfaces

## 1A. Implementation Surface Authority

Packet-1 implementation must land first in the authoritative runtime-summary and protocol-ledger paths.

Authoritative backend surfaces for packet 1 are:
1. `orket/runtime/execution_pipeline.py` for orchestration and finalize-path propagation
2. `orket/runtime/run_summary.py` for canonical packet-1 summary generation and reconstruction
3. `orket/adapters/storage/async_protocol_run_ledger.py` for packet-1 ledger-fact emission before summary generation

Compatibility-only surfaces may be updated only as needed to preserve parity:
1. `orket/adapters/storage/async_dual_write_run_ledger.py`
2. `orket/adapters/storage/async_repositories.py`
3. `orket/logging.py` for runtime diagnostic artifact fallback under `agent_output/observability/runtime_events.jsonl`

Dual-write or legacy-ledger support must remain compatibility-only and must not become a second source of packet-1 semantics.

## 2. Bounded Deliverables

This plan is limited to:
1. packet-1 `run_summary.json` extension support under one additive extension object
2. deterministic primary-output selection
3. provenance envelope emission
4. truth-classification emission with machine-readable classification basis
5. packet-1 defect detection for:
   1. `silent_path_mismatch`
   2. `silent_repaired_success`
   3. `silent_degraded_success`
   4. `silent_unrecorded_fallback`
   5. `classification_divergence`
6. packet-1 conformance surface and emission-failure handling
7. contract, integration, and end-to-end proof for the above
8. at least one example artifact or transcript showing the new truth surfaces

## 3. Explicit Non-Goals

Do not include in this packet:
1. structured repair ledger history
2. narration-to-effect audit beyond packet-1 defect families
3. cancellation truth beyond packet-1 applicability behavior already locked in the requirements
4. idempotency-key expansion outside packet-1 needs
5. high-stakes evidence-first mode
6. source-attribution contract
7. voice truth contract
8. artifact-generation provenance contract
9. memory and trust-policy work from Phase D
10. promotion and governance work from Phase E
11. provider-expansion or unrelated UI/product work

If implementation pressure requires any of the above, stop and reopen scope explicitly instead of folding it into packet-1.

## 4. Exit Artifacts

Packet-1 is not complete without all of:
1. runtime implementation emitting the packet-1 extension surface
2. updated durable contract in `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` if implementation clarifies wording without widening scope
3. contract tests for packet-1 vocabulary, precedence, basis vocabulary, and defect taxonomy
4. integration tests for propagation from ledger facts to `run_summary.json`
5. end-to-end proof covering user-visible packet-1 behavior
6. reconstruction proof showing emitted and reconstructed packet-1 content match
7. at least one example artifact or transcript showing provenance, classification, defects, and conformance surfaces together
8. a closeout artifact inventory identifying:
   1. updated runtime files
   2. contract test files
   3. integration test files
   4. end-to-end proof artifact
   5. reconstruction proof artifact
   6. example transcript or artifact

## 5. Execution Order

Implement in this order:
1. finalize the packet-1 extension shape and namespacing in runtime-owned outputs
2. implement primary-output selection and packet-1 applicability behavior
3. emit ledger-recorded facts required for packet-1 reconstruction completeness
4. emit provenance envelope fields and execution-profile stamping
5. implement truth-classification assignment and classification-basis recording
6. implement packet-1 defect detection and conformance recording
7. implement packet-1 emission-failure reporting path
8. complete proof and example artifact work

Execution gate:
1. W3 must not implement classification, defect, or conformance recording until W1 has locked the packet-1 extension shape and W1/W2 have emitted every ledger fact W3 depends on.

## 6. Workstreams

### W1 - Summary Surface And Reconstruction

Tasks:
1. define the concrete packet-1 extension object in `run_summary.json`
2. preserve additive compatibility for existing summary consumers
3. ensure packet-1 reconstruction uses ledger state only, per accepted contract
4. add any missing ledger-recorded derived facts needed for classification and defect reconstruction

Acceptance:
1. packet-1 extension emits under one additive namespaced surface
2. reconstructed packet-1 content matches emitted packet-1 content
3. no packet-1 reconstruction path depends on artifact bytes, prompt parsing, or logs

### W2 - Boundary Selection And Provenance

Tasks:
1. implement deterministic primary-output selection
2. implement no-output behavior for terminal runs with no selected boundary
3. emit provenance envelope fields:
   1. intended and actual provider/model/profile
   2. path mismatch and stable mismatch reason
   3. retry/repair/fallback indicators
   4. execution profile

Acceptance:
1. packet-1 selects at most one primary output boundary
2. no-output terminal runs emit provenance without fabricated classification
3. provenance is attributable to ledger-recorded or ledger-derived runtime facts

### W3 - Classification, Defects, And Conformance

Tasks:
1. implement the fixed classification precedence and assignment ladder
2. emit `classification_applicable`, `truth_classification`, and `classification_basis`
3. implement minimum packet-1 defect triggers
4. emit canonical `defects` and `packet1_conformance` surfaces
5. implement emission-failure fallback reporting through ledger error event plus runtime diagnostic artifact

Implementation rule:
1. The classification ladder, classification-basis vocabulary, and packet-1 defect triggers are defined by `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` and must be adopted verbatim without reinterpretation or widening during implementation.

Conformance authority:
1. On successful summary emission, canonical `packet1_conformance` is emitted in the packet-1 `run_summary.json` extension.
2. Only when summary emission fails does the runtime diagnostic artifact become the authoritative packet-1 conformance surface for that run.

Acceptance:
1. packet-1 emits one deterministic classification when classification is applicable
2. packet-1 detects the minimum defect families mechanically
3. packet-1 conformance becomes `non_conformant` on emission failure without altering terminal run status

### W4 - Proof And Example Artifacts

Tasks:
1. add contract tests for schema, vocabulary, precedence, basis vocabulary, and defect taxonomy
2. add integration tests for ledger-to-summary propagation
3. add end-to-end proof for user-visible packet-1 behavior
4. publish at least one example artifact or transcript

Required proof cases:
1. `direct`
2. `inferred`
3. `estimated`
4. `repaired`
5. `degraded`
6. silent-fallback detection
7. `classification_divergence`
8. packet-1 emission failure
9. finalized run with no selected primary output boundary
10. negative detector case with no packet-1 defect

Acceptance:
1. proof truth is labeled accurately as contract, integration, or end-to-end
2. no mock-only proof is represented as runtime conformance
3. at least one example artifact makes the packet-1 surfaces legible without code inspection

## 6A. Proof Commands And Output Locations

Canonical proof command families for packet-1 are:
1. reconstruction and summary proof:
   1. `python -m pytest tests/runtime/test_run_summary.py -q`
   2. expected runtime outputs anchor at `runs/<run_id>/run_summary.json`
   3. expected reconstruction inputs anchor at `runs/<run_id>/events.log`
2. finalize-path and emission-failure proof:
   1. `python -m pytest tests/application/test_execution_pipeline_run_ledger.py -q`
   2. expected runtime outputs anchor at `runs/<run_id>/run_summary.json`
   3. expected failure-path observability anchor at `agent_output/observability/runtime_events.jsonl`
3. end-to-end packet-1 user-visible proof:
   1. `python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard -q`
   2. expected user-visible verification anchor at `agent_output/verification/runtime_verification.json`
   3. expected run-summary anchor at `runs/<run_id>/run_summary.json`
4. example artifact or transcript staging:
   1. stage under one stable packet-1 proof directory in `benchmarks/staging/General/`
   2. do not leave the example artifact or transcript only in ad hoc workspace output paths

## 7. Completion Gate

Packet-1 is complete only when:
1. covered runs emit the packet-1 extension under `run_summary.json`
2. no-output terminal runs emit provenance, defects, and conformance without fabricated classification
3. packet-1 reconstruction matches emitted packet-1 content
4. minimum defect families are machine-detectable and reportable
5. packet-1 emission failure is surfaced through the defined fallback authority path
6. proof and example-artifact exit artifacts exist and are truthfully labeled
7. proof covers both success-path and non-success or failure-path behavior; packet-1 is not complete if proof covers only success-path runs

## 8. Stop Conditions

Stop and reopen scope if implementation requires:
1. structured repair-history lineage beyond occurrence-level attribution
2. broader narration-to-effect auditing
3. source attribution or evidence-first synthesis
4. voice or artifact-generation provenance
5. policy changes to terminal run status semantics
6. widening `run_summary.json` reconstruction beyond accepted packet-1 contract
7. widening ledger schema or vocabulary beyond accepted packet-1 facts, reasons, or taxonomy values without prior contract update
