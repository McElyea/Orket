# TRH03142026 Phase C Requirements

Last updated: 2026-03-14
Status: Accepted (implementation plan active)
Owner: Orket Core
Canonical implementation plan: `docs/projects/truthful-runtime/TRH03142026-PHASE-C-IMPLEMENTATION-PLAN.md`
Extracted durable contract: `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`

## Purpose

Define the bounded first Phase C requirements packet for truthful runtime hardening before Orket writes an implementation plan.

This lane exists to answer one question first:
what exactly must the first Phase C packet do for provenance, truth classification, and silent fallback detection?

## Source Inputs

1. `AGENTS.md`
2. `docs/CONTRIBUTOR.md`
3. `docs/ROADMAP.md`
4. `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-IMPLEMENTATION-PLAN.md`
5. `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-C-IMPLEMENTATION-PLAN.md`
6. `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`
7. `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
8. `docs/specs/PROTOCOL_DETERMINISM_CONTROL_SURFACE.md`
9. `docs/specs/PROTOCOL_ERROR_CODE_REGISTRY.md`
10. `docs/specs/RUNTIME_INVARIANTS.md`
11. `docs/TESTING_POLICY.md`
12. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`

## Current Truth

1. Orket has strengthened runtime determinism, protocol enforcement, compare semantics, and published-proof truthfulness, but it still lacks a bounded accepted Phase C packet for provenance and fallback truth.
2. The staged truthful-runtime hardening authority already identifies provenance and fallback truth as the critical path before later trust/promotion work.
3. No accepted active requirements doc yet defines:
   1. the minimum provenance envelope for the first packet
   2. the exact first-packet meaning of `direct|inferred|estimated|repaired|degraded`
   3. the minimum silent fallback defect classes that must become machine-detectable
4. The first packet must stay smaller than the full original Phase C deliverable list.

## Problem Statement

Orket needs an active, bounded, requirements-first Phase C lane so future implementation work is driven by an accepted packet definition instead of a broad staged backlog.

## Scope

In scope:
1. execution provenance envelope requirements for the first packet
2. response truth classification requirements for the first packet
3. silent fallback detector and defect-classification requirements for the first packet
4. proof and example-artifact requirements for eventual implementation acceptance
5. explicit deferred items that remain outside the first packet

Out of scope:
1. full structured repair ledger scope if it is not required to support the first packet
2. high-stakes evidence-first mode beyond identifying it as a deferred Phase C surface
3. voice truth and artifact generation provenance beyond deferral notes
4. memory and trust policy work from Phase D
5. promotion and operational governance work from Phase E
6. any implementation sequencing or task breakdown beyond what is needed to evaluate requirements completeness

## Definitions

1. Provenance envelope: the compact runtime-owned record that states what execution path actually occurred for the covered run or response boundary.
2. Truth classification: the bounded runtime label that states how strong the final response claim is relative to the actual execution path.
3. Silent fallback: a material runtime path change, repair, substitution, or degradation that occurred without being surfaced in the machine-readable record or user-visible contract where required.
4. First packet: the smallest accepted Phase C slice reopened by this lane, not the full future-state Phase C program.
5. Primary output boundary: the single selected final user-visible output boundary for packet 1 when one exists.
6. Classification basis: the machine-readable rule and evidence category that explain why packet 1 assigned the final truth classification.
7. Packet-1 conformance: the machine-readable status indicating whether packet-1 surfaces were emitted and satisfy this contract.

## Bounded Packet

The first accepted Phase C packet is limited to:
1. one compact execution provenance envelope
2. one bounded truth-classification contract
3. one silent fallback detector and defect-classification surface
4. proof and example artifacts that show those surfaces operating together

The first packet is explicitly not the whole of Phase C.

For packet 1, this requirements draft must decide rather than defer:
1. the canonical runtime-owned storage surface
2. the minimum covered boundary
3. the minimum stable packet-1 defect families
4. the deterministic primary-output selection rule
5. the no-output applicability behavior
6. the minimum packet-1 extension shape
7. the machine-readable packet-1 conformance surface
8. the machine-readable classification basis surface

## Planning Locks

1. The canonical runtime-owned storage surface for packet 1 is a `run_summary.json` extension.
2. Packet 1 minimum coverage is fixed to:
   1. the finalized run surface
   2. the selected primary output boundary when one exists
3. Primary-output selection authority order is:
   1. explicit completion contract
   2. direct response surface
   3. explicitly designated primary artifact
   4. none
4. Secondary generated operator-facing artifacts are out of scope for packet 1 unless one of those artifacts is itself the primary output.
5. Minimum packet-1 extension shape is:
   1. `schema_version`
   2. `provenance`
   3. `classification`
   4. `defects`
   5. `packet1_conformance`
6. Packet-1 extensions must be additive and must not break `run_summary.json` consumers that ignore unknown fields.
7. Packet 1 minimum stable packet-1 defect families are:
   1. `silent_path_mismatch`
   2. `silent_repaired_success`
   3. `silent_degraded_success`
   4. `silent_unrecorded_fallback`
   5. `classification_divergence`

## Packet-1 Reconstruction And Emission Compatibility

1. Packet 1 depends directly on the run-summary reconstruction authority in `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`.
2. All facts required to reconstruct packet-1 classification and defect outcomes must be recorded in ledger state before summary generation.
3. Packet-1 reconstruction must never require artifact byte inspection, log parsing, or prompt inspection.
4. If packet-1 classification or defect logic depends on information derived from output content during execution, those derived facts must be written to the ledger before summary generation.
5. Packet-1 reconstruction must satisfy `reconstructed packet-1 extension == emitted packet-1 extension`.
6. If packet-1 summary emission fails:
   1. terminal run status remains unchanged
   2. the original run result remains valid
   3. packet-1 conformance becomes `non_conformant`
7. Packet-1 emission failure must be recorded through:
   1. a ledger error event
   2. a runtime diagnostic artifact
8. When the packet-1 summary extension is absent because summary emission failed, the runtime diagnostic artifact is the authoritative packet-1 conformance surface for that run.
9. Packet-1 summary emission failure must never silently omit packet-1 surfaces.
10. Packet 1 must expose a machine-readable `packet1_conformance` surface.
11. `packet1_conformance.status` must be one of:
   1. `conformant`
   2. `non_conformant`
12. When `packet1_conformance.status = non_conformant`, reasons must be represented as unique, deterministically ordered stable identifiers.
13. Minimum `packet1_conformance` reasons must include:
   1. `packet1_emission_failure`
   2. `classification_divergence`
   3. `silent_path_mismatch`
   4. `silent_repaired_success`
   5. `silent_degraded_success`
   6. `silent_unrecorded_fallback`

## Packet-1 Applicability And Surface Normalization

1. Packet 1 applies to successful, failed, cancelled, and incomplete terminal runs.
2. If a finalized run has a selected primary output boundary, packet 1 must emit provenance, truth classification, defect detection, and packet-1 conformance surfaces.
3. If a finalized run has no selected primary output boundary, packet 1 must emit provenance, defect detection, and packet-1 conformance surfaces.
4. If a finalized run has no selected primary output boundary:
   1. `classification_applicable` must be `false`
   2. `truth_classification` must be omitted
   3. `classification_basis` must be omitted
5. Packet 1 must not fabricate truth classification when no primary output boundary exists.
6. `primary_output_kind` must be one of:
   1. `response`
   2. `artifact`
   3. `none`
7. When `primary_output_kind = none`, `primary_output_id` must be omitted.
8. Optional packet-1 fields are omitted rather than set to `null`.

## Requirements

### RC1: Execution Provenance Envelope

1. The first packet must use one canonical runtime-owned storage surface for provenance, truth, and silent-fallback attachment, and that surface is a `run_summary.json` extension.
2. The `run_summary.json` extension is the authoritative packet-1 storage surface. Receipts, logs, or other artifacts may support or reference it, but they are not the canonical packet-1 storage surface.
3. The first packet must define one deterministic primary-output selection rule for the covered boundaries fixed in `Planning Locks`.
4. If no authority level selects a unique primary output boundary, `primary_output_kind` must be `none`.
5. Within direct response surfaces, precedence is:
   1. structured protocol or API response surface
   2. CLI or terminal completion output surface
6. The first packet must define one runtime-owned provenance envelope for the covered boundaries fixed in `Planning Locks`.
7. The provenance envelope must record the actual executed path, not only the configured intent.
8. Minimum first-packet fields must include:
   1. `run_id` or equivalent execution identity
   2. terminal run status for the finalized run surface
   3. `primary_output_kind`
   4. `primary_output_id` or equivalent stable boundary identifier when a primary output boundary exists
   5. intended provider when provider selection is materially policy-selected
   6. intended model when model selection is materially policy-selected
   7. intended profile when profile selection is materially policy-selected
   8. actual provider
   9. actual model
   10. actual profile when materially relevant
   11. `path_mismatch` indicator when intended and actual execution paths differ materially
   12. `mismatch_reason` or equivalent explicit stable mismatch code when path mismatch occurs
   13. `retry_occurred`
   14. `repair_occurred`
   15. `fallback_occurred`
   16. `execution_profile`
   17. the final truth classification for the covered boundary when classification is applicable
9. Retries, repairs, and fallbacks must be recorded as separate attributable indicators, not as one merged occurrence field.
10. `execution_profile` must be one of:
   1. `normal`
   2. `fallback`
   3. `reduced_capability`
11. `mismatch_reason` must be a stable code rather than free-form prose.
12. The provenance envelope must be attributable to deterministic ledger-recorded or ledger-derived runtime facts rather than free-form narration.
13. Provenance facts required by packet 1 must not exist only as prose in logs, prompts, or operator commentary.
14. If the intended path and actual path differ materially, the envelope must preserve both the intended path and the actual executed path or an equivalent explicit mismatch representation that is sufficient for deterministic proof and defect attachment.
15. The first packet does not require a full historical repair ledger if the run summary extension plus existing ledger-recorded runtime facts can support bounded attribution truthfully.

### RC2: Truth Classification Contract

1. The first packet must define these truth-classification values and no others:
   1. `direct`
   2. `inferred`
   3. `estimated`
   4. `repaired`
   5. `degraded`
2. Exactly one final truth-classification value must apply at each covered boundary when classification is applicable.
3. Truth classification for packet 1 must be attached at minimum to:
   1. the finalized run surface when classification is applicable
   2. the selected primary output boundary when one exists
4. The first packet must define a deterministic precedence rule and deterministic assignment conditions. Classification must not depend on reviewer judgment alone.
5. The packet-1 classification precedence is fixed and must be evaluated in this order:
   1. `degraded`
   2. `repaired`
   3. `estimated`
   4. `inferred`
   5. `direct`
6. Classification must be determined by the following evaluation order:
   1. `degraded` if `fallback_occurred` is true or the final covered output was produced on a reduced-capability or fallback execution path
   2. else `repaired` if `repair_occurred` is true and validator-driven correction materially changed the accepted final output
   3. else `estimated` if the final covered output explicitly communicates approximation or bounded uncertainty
   4. else `inferred` if the final covered output synthesizes from runtime evidence beyond direct restatement without claiming approximation
   5. else `direct`
7. Retry-only behavior that does not change the final execution path must not alter classification.
8. If classification evaluation would produce divergent results across covered boundaries when packet 1 requires one canonical truth classification, the runtime must emit `classification_divergence` and must not silently choose one value.
9. Packet-1 classification records must include:
   1. `classification_applicable`
   2. `truth_classification` when classification is applicable
   3. `classification_basis` when classification is applicable
10. `classification_basis.rule` must be one of:
   1. `direct`
   2. `inferred`
   3. `estimated`
   4. `repaired`
   5. `degraded`
11. `classification_basis.evidence_source` must be one of:
   1. `direct_execution`
   2. `runtime_evidence`
   3. `estimation_marker`
   4. `validator_repair`
   5. `fallback_or_reduced_capability`
12. `classification_basis` must not embed artifact content or raw evidence inputs.
13. If no primary output boundary exists:
   1. `classification_applicable` must be `false`
   2. `truth_classification` must be omitted
   3. `classification_basis` must be omitted
14. User-visible or operator-visible surfaces must not imply a stronger class than the recorded truth classification for the covered boundary and must not imply classified success when `classification_applicable = false`.

### RC3: Silent Fallback Detector

1. The first packet must define silent fallback as a detectable defect class, not a narrative concern only.
2. Packet-1 defect family identifiers are stable packet-1 runtime taxonomy identifiers and must include:
   1. `silent_path_mismatch`
   2. `silent_repaired_success`
   3. `silent_degraded_success`
   4. `silent_unrecorded_fallback`
   5. `classification_divergence`
3. Packet-1 defect detection rules are:
   1. `silent_path_mismatch` if the actual provider, model, or profile differs materially from the intended path and no machine-readable mismatch indicator exists at the covered boundary
   2. `silent_repaired_success` if `repair_occurred` is true and the output boundary presents the result as normal success
   3. `silent_degraded_success` if `execution_profile = reduced_capability` or `fallback_occurred = true` and the output boundary presents the result as normal success
   4. `silent_unrecorded_fallback` if a fallback execution path is detected and the `fallback_occurred` indicator is absent from the provenance envelope
   5. `classification_divergence` if finalized run-surface classification evaluation differs from primary-output classification evaluation when packet 1 requires a single canonical truth classification
4. Each detected silent fallback or packet-1 defect must map to one of the stable packet-1 defect families above or to a later explicitly accepted extension of that taxonomy.
5. The first packet may defer broader narration-to-effect audit coverage if the minimum packet-1 defect families above are still machine-detectable and reportable.
6. Detection must produce a reportable runtime artifact, event, or equivalent machine-readable record rather than only log prose.
7. A packet-1 defect must not rely on log-only prose for detection or reporting.
8. Silent fallback detection artifacts must be joinable to the provenance envelope through `run_id` or an equivalent stable runtime-owned key.
9. The canonical packet-1 defects surface must include:
   1. `defects_present`
   2. `defect_families`
10. A conformant packet-1 no-defect record must set:
   1. `defects_present = false`
   2. `defect_families = []`
11. Absence of the packet-1 `defects` block is invalid.
12. `defect_families` must be unique and deterministically ordered.
13. A packet-1 defect is explicitly surfaced when it appears in the canonical packet-1 `defects` block. User-visible surfaces are not required to repeat defect information but must not contradict packet-1 classification or imply stronger success semantics than the packet-1 record.

### RC4: Proof Contract For The First Packet

1. The eventual implementation lane must prove the first packet with:
   1. contract tests for vocabulary, schema, and precedence rules
   2. integration tests for propagation of provenance/truth/fallback records through the runtime path
   3. at least one end-to-end proof showing the three surfaces together on a user-visible flow
2. The eventual implementation lane must include at least one example artifact or transcript that makes the new surfaces legible without code inspection.
3. Structural-only proof is insufficient to claim runtime truth for the implemented packet.
4. Live proof is not required by this requirements draft itself, but any later implementation lane must label proof mode truthfully and must not present mock-only proof as runtime conformance.
5. The proof set for the eventual implementation lane must include at minimum:
   1. one normal-path case resulting in `direct` or `inferred`
   2. one `repaired` case
   3. one `degraded` or fallback-path case
   4. one silent-fallback detection case
   5. one `classification_divergence` case
   6. one packet-1 emission failure case
   7. one finalized run with no selected primary output boundary
6. Contract-level classification and precedence coverage must exercise all five truth-classification values even if end-to-end proof remains bounded to the minimum cases above.

### RC5: Explicit Deferrals

The following Phase C items remain deferred unless later accepted into scope explicitly:
1. full structured repair ledger
2. full narration-to-effect audit coverage
3. cancellation truth path
4. full idempotency-key policy
5. high-stakes evidence-first synthesis mode
6. source-attribution contract
7. voice truth contract
8. artifact-generation provenance contract

## Packet-1 Boundary And Storage Decisions

1. The canonical runtime-owned packet-1 storage surface is a `run_summary.json` extension.
2. Packet 1 depends directly on `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md` and must remain compatible with the run-summary reconstruction contract defined there.
3. Packet-1 truth classification is required at:
   1. the finalized run surface when classification is applicable
   2. the selected primary output boundary when one exists
4. If no primary output boundary exists:
   1. `classification_applicable` must be `false`
   2. `truth_classification` must be omitted
   3. `classification_basis` must be omitted
5. Secondary generated operator-facing artifacts remain deferred unless one of those artifacts is itself the primary output.
6. Packet 1 minimum stable packet-1 defect families are:
   1. `silent_path_mismatch`
   2. `silent_repaired_success`
   3. `silent_degraded_success`
   4. `silent_unrecorded_fallback`
   5. `classification_divergence`
7. Packet 1 does not require a minimal repair-history pointer if the run summary extension plus existing ledger-recorded runtime facts can truthfully attribute repair occurrence.

## Implementation Activation

The user accepted this requirements lane and requested implementation planning on 2026-03-14.

Active implementation authority now lives in:
1. `docs/projects/truthful-runtime/TRH03142026-PHASE-C-IMPLEMENTATION-PLAN.md`

Extracted durable packet-1 contract now lives in:
1. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
