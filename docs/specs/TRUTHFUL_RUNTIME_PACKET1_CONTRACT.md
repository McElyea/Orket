# Truthful Runtime Packet-1 Contract

Last updated: 2026-03-15
Status: Active
Owner: Orket Core
Canonical requirements source: `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/TRH03142026-PHASE-C-REQUIREMENTS.md`
Related authority:
1. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
2. `docs/specs/TRUTHFUL_RUNTIME_REPAIR_LEDGER_CONTRACT.md`
3. `docs/architecture/CONTRACT_DELTA_TRUTHFUL_RUNTIME_PACKET1_BOUNDARY_REALIGNMENT_2026-03-15.md`

## Purpose

Define the durable packet-1 runtime truth contract extracted from the accepted Phase C bounded requirements.

This contract governs the minimum runtime-owned truth surfaces for:
1. execution provenance
2. truth classification
3. silent fallback defect detection
4. packet-1 conformance

Packet-1 proof artifacts demonstrate correctness of runtime truth surfaces. They do not claim semantic quality of generated artifacts.

Implementation archive:
1. `docs/projects/archive/truthful-runtime/TRH03142026-PACKET1/TRH03142026-PHASE-C-IMPLEMENTATION-PLAN.md`

Broader Phase C continuation and the active packet-2 repair-ledger slice live in:
1. `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-C-IMPLEMENTATION-PLAN.md`

## Scope

In scope:
1. packet-1 `run_summary.json` extension contract
2. packet-1 provenance envelope contract
3. packet-1 truth-classification contract
4. packet-1 defect taxonomy and trigger contract
5. packet-1 conformance contract

Out of scope:
1. structured repair ledger history
2. narration-to-effect audit beyond packet-1 defect families
3. source attribution and evidence-first mode
4. voice truth and artifact-generation provenance
5. Phase D memory and trust-policy work
6. Phase E promotion and governance work

## Canonical Surface

1. Packet 1 uses one canonical runtime-owned storage surface: a `run_summary.json` extension.
2. Packet-1 additions must live under one additive extension object and must not break readers that ignore unknown fields.
3. Minimum packet-1 extension shape is:
   1. `schema_version`
   2. `provenance`
   3. `classification`
   4. `defects`
   5. `packet1_conformance`

## Reconstruction Rule

1. Packet 1 must remain compatible with the `run_summary.json` authority in `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`.
2. All facts required to reconstruct packet-1 classification and defect outcomes must be recorded in ledger state before summary generation.
3. Packet-1 reconstruction must never require artifact byte inspection, log parsing, or prompt inspection.
4. If packet-1 classification or defect logic depends on content-derived facts observed during execution, those derived facts must be written to the ledger before summary generation.
5. Packet-1 reconstruction must satisfy:
   1. `reconstructed packet-1 extension == emitted packet-1 extension`

## Applicability And Boundary Selection

1. Packet 1 applies to successful, failed, cancelled, and incomplete terminal runs.
2. Covered boundaries are:
   1. the finalized run surface
   2. the selected primary output boundary when one exists
3. Primary-output selection authority order is:
   1. explicit completion contract
   2. explicitly designated work artifact
   3. direct response surface
   4. runtime verification artifact fallback
   5. none
4. When multiple candidate work artifacts exist, the runtime must designate one deterministically from runtime-owned artifact-provenance facts using:
   1. greatest `turn_index`
   2. then latest `produced_at`
   3. then lexical `artifact_path`
5. Within direct response surfaces, precedence is:
   1. structured protocol or API response surface
   2. CLI or terminal completion output surface
6. `primary_output_kind` must be one of:
   1. `response`
   2. `artifact`
   3. `none`
7. When `primary_output_kind = none`, `primary_output_id` must be omitted.
8. If no primary output boundary exists:
   1. `classification_applicable` must be `false`
   2. `truth_classification` must be omitted
   3. `classification_basis` must be omitted
9. Packet 1 must not fabricate truth classification when no primary output boundary exists.
10. Optional packet-1 fields are omitted rather than set to `null`.

## Provenance Contract

1. Packet 1 must emit one runtime-owned provenance envelope.
2. Minimum provenance fields are:
   1. `run_id`
   2. terminal run status for the finalized run surface
   3. `primary_output_kind`
   4. `primary_output_id` when a primary output boundary exists
   5. intended provider
   6. intended model
   7. intended profile
   8. actual provider
   9. actual model
   10. actual profile
   11. `path_mismatch`
   12. `mismatch_reason`
   13. `retry_occurred`
   14. `repair_occurred`
   15. `fallback_occurred`
   16. `execution_profile`
   17. final truth classification when classification is applicable
3. `execution_profile` must be one of:
   1. `normal`
   2. `fallback`
   3. `reduced_capability`
4. `mismatch_reason` must be a stable code rather than free-form prose.
5. Provenance facts must be attributable to deterministic ledger-recorded or ledger-derived runtime facts.
6. Provenance facts must not exist only as prose in logs, prompts, or operator commentary.
7. When required intended-path provenance data is absent, the runtime must emit the stable token `missing`.
8. Required provenance fields must not emit implementation placeholder values such as `None` or `unknown`.

## Truth-Classification Contract

1. Packet 1 defines exactly these truth-classification values:
   1. `direct`
   2. `inferred`
   3. `estimated`
   4. `repaired`
   5. `degraded`
2. Exactly one final truth-classification value applies at each covered boundary when classification is applicable.
3. Classification precedence is fixed and must be evaluated in this order:
   1. `degraded`
   2. `repaired`
   3. `estimated`
   4. `inferred`
   5. `direct`
4. Classification assignment must use this evaluation order:
   1. `degraded` if `fallback_occurred` is true or the final covered output was produced on a reduced-capability or fallback execution path
   2. else `repaired` if `repair_occurred` is true and validator-driven correction materially changed the accepted final output
   3. else `estimated` if the final covered output explicitly communicates approximation or bounded uncertainty
   4. else `inferred` if the final covered output synthesizes from runtime evidence beyond direct restatement without claiming approximation
   5. else `direct`
5. Retry-only behavior that does not change the final execution path must not alter classification.
6. Classification records must include:
   1. `classification_applicable`
   2. `truth_classification` when classification is applicable
   3. `classification_basis` when classification is applicable
7. `classification_basis.rule` must be one of:
   1. `direct`
   2. `inferred`
   3. `estimated`
   4. `repaired`
   5. `degraded`
8. `classification_basis.evidence_source` must be one of:
   1. `direct_execution`
   2. `runtime_evidence`
   3. `estimation_marker`
   4. `validator_repair`
   5. `fallback_or_reduced_capability`
9. `classification_basis` must not embed artifact content or raw evidence inputs.
10. User-visible or operator-visible surfaces must not imply a stronger class than the recorded truth classification and must not imply classified success when `classification_applicable = false`.

## Defect Contract

1. Packet-1 defect families are stable runtime taxonomy identifiers:
   1. `silent_path_mismatch`
   2. `silent_repaired_success`
   3. `silent_degraded_success`
   4. `silent_unrecorded_fallback`
   5. `classification_divergence`
2. Detection rules are:
   1. `silent_path_mismatch` if the actual provider, model, or profile differs materially from the intended path and no machine-readable mismatch indicator exists at the covered boundary
   2. `silent_repaired_success` if `repair_occurred` is true and the output boundary presents the result as normal success
   3. `silent_degraded_success` if `execution_profile = reduced_capability` or `fallback_occurred = true` and the output boundary presents the result as normal success
   4. `silent_unrecorded_fallback` if a fallback execution path is detected and the `fallback_occurred` indicator is absent from the provenance envelope
   5. `classification_divergence` if finalized run-surface classification evaluation differs from primary-output classification evaluation when packet 1 requires one canonical truth classification
3. The canonical `defects` block must include:
   1. `defects_present`
   2. `defect_families`
4. A conformant no-defect record must set:
   1. `defects_present = false`
   2. `defect_families = []`
5. Absence of the packet-1 `defects` block is invalid.
6. `defect_families` must be unique and deterministically ordered.
7. A packet-1 defect is explicitly surfaced when it appears in the canonical packet-1 `defects` block.

## Packet-1 Conformance Contract

1. Packet 1 must expose a machine-readable `packet1_conformance` surface.
2. `packet1_conformance.status` must be one of:
   1. `conformant`
   2. `non_conformant`
3. When `packet1_conformance.status = non_conformant`, reasons must be unique, deterministically ordered stable identifiers.
4. Minimum `packet1_conformance` reasons are:
   1. `packet1_emission_failure`
   2. `classification_divergence`
   3. `silent_path_mismatch`
   4. `silent_repaired_success`
   5. `silent_degraded_success`
   6. `silent_unrecorded_fallback`
5. Packet-1 defects do not change terminal run status.

## Emission Failure Semantics

1. If packet-1 summary emission fails:
   1. terminal run status remains unchanged
   2. the original run result remains valid
   3. packet-1 conformance becomes `non_conformant`
2. Emission failure must be recorded through:
   1. a ledger error event
   2. a runtime diagnostic artifact
3. When the packet-1 summary extension is absent because summary emission failed, the runtime diagnostic artifact is the authoritative packet-1 conformance surface for that run.
4. Packet-1 summary emission failure must never silently omit packet-1 surfaces.
