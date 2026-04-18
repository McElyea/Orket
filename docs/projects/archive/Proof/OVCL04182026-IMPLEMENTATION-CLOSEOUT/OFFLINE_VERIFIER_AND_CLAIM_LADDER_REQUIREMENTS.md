# Offline Verifier And Claim Ladder Requirements

Last updated: 2026-04-18
Status: Completed requirements - archived with implementation closeout
Owner: Orket Core

Canonical plan: `docs/projects/archive/Proof/OVCL04182026-IMPLEMENTATION-CLOSEOUT/OFFLINE_VERIFIER_AND_CLAIM_LADDER_REQUIREMENTS_PLAN.md`
Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/04_OFFLINE_VERIFIER_AND_CLAIM_LADDER.md`
Primary dependency: `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
Primary dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Primary dependency: `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
Primary dependency: `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`

## Purpose

Define accepted requirements for the offline verifier and claim ladder.

The offline verifier must answer:

```text
What does this evidence prove?
What does it fail to prove?
What claim tier is allowed?
Which higher claims are forbidden by missing or contradictory evidence?
```

It must not run the workflow, call a model, mutate workflow state, inspect undeclared runtime state, or upgrade claims beyond available evidence.

## Resolved Requirements Decisions

1. The first offline verifier MUST accept raw witness bundles, single trusted-run verifier reports, and trusted-run campaign reports as separate input modes.
2. A same-change durable spec extraction SHOULD create `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md` after user acceptance and before implementation.
3. The first standalone offline-verifier report path SHOULD be `benchmarks/results/proof/offline_trusted_run_verifier.json`.
4. The existing `scripts/proof/verify_trusted_run_witness_bundle.py` SHOULD remain the bundle verifier; the offline claim evaluator SHOULD be a separate command after acceptance.
5. `replay_deterministic` MUST remain future-gated until explicit replay evidence satisfies `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.
6. `text_deterministic` MUST require explicit byte identity or declared output-hash identity on the same compare scope, plus the policy-required verdict or replay evidence.
7. Negative examples SHOULD be table-driven/generated first. Stored fixtures are optional only after the generated cases prove the corruption contract.
8. `claim_tier` alone MUST NOT be treated as a success claim. Failure output MUST also expose claim status, observed result, and missing evidence.

## Boundary Requirements

OVCL-REQ-001: The first offline verifier MUST be scoped to `trusted_run_productflow_write_file_v1`.

OVCL-REQ-002: The first verifier surface MUST evaluate evidence for `trusted_run_witness_report.v1` and MUST NOT create a second truth surface for the same ProductFlow witness result.

OVCL-REQ-003: The verifier MUST be side-effect free with respect to workflow state, durable control-plane records, model/provider calls, runtime execution, replay execution, and artifact publication.

OVCL-REQ-004: The verifier MAY write only its own report artifact, and rerunnable JSON output MUST use the repository diff-ledger writer convention.

OVCL-REQ-005: The verifier MUST NOT run the workflow, call a model, perform replay execution, mutate durable control-plane records, or treat logs, review packages, graphs, or Packet projections as authority.

OVCL-REQ-006: The verifier MUST inspect evidence only from declared inputs and their declared references.

OVCL-REQ-007: The verifier MUST fail closed on unsupported schema versions.

OVCL-REQ-008: The verifier MUST preserve `compare_scope`, `operator_surface`, policy identity, and evidence references in every success, downgrade, and failure report.

OVCL-REQ-009: If even the minimum lab evidence is invalid, the verifier MUST set `claim_status=blocked`, `claim_tier=non_deterministic_lab_only`, and `allowed_claims=[]` instead of presenting lab status as proven.

## Input Mode Requirements

OVCL-REQ-010: The verifier MUST support these input modes:

| Input mode | Required source schema | Purpose | Highest first-slice claim allowed |
|---|---|---|---|
| `bundle` | `trusted_run.witness_bundle.v1` | Recompute contract verdict, invariant model, and substrate model from one raw bundle. | `non_deterministic_lab_only` |
| `single_report` | `trusted_run_witness_report.v1` without campaign fields | Inspect one already-computed verifier report. | `non_deterministic_lab_only` |
| `campaign_report` | `trusted_run_witness_report.v1` with campaign comparison fields | Inspect repeated verifier evidence and stability checks. | `verdict_deterministic` |
| `replay_report` | future replay evidence schema | Inspect replay evidence without running replay. | `replay_deterministic` |
| `text_identity_report` | future text identity evidence schema | Inspect byte/hash identity evidence. | `text_deterministic` |

OVCL-REQ-011: `bundle` input MUST include or reference:

1. witness bundle schema identity
2. `bundle_id`, governed `run_id`, and locator `session_id`
3. compare scope
4. operator surface
5. policy and configuration refs
6. authority lineage evidence
7. observed effect evidence
8. contract verdict or enough evidence to recompute it
9. invariant model output or enough evidence to recompute it
10. control-plane witness substrate output or enough evidence to recompute it

OVCL-REQ-012: `single_report` input MUST include:

1. report schema identity
2. observed path
3. observed result
4. claim tier, and claim status when present
5. compare scope
6. operator surface
7. bundle id or report id
8. contract verdict digest
9. invariant model signature digest
10. substrate signature digest
11. missing evidence list
12. side-effect-free verification field

OVCL-REQ-013: `campaign_report` input MUST include:

1. report schema identity
2. run count
3. successful verification count
4. included bundle report refs or embedded bundle reports
5. stable verdict signature digest set
6. stable invariant model signature digest set
7. stable substrate signature digest set
8. stable must-catch outcome set
9. side-effect-free verification field
10. missing evidence list
11. bundle refs or evidence refs when available

OVCL-REQ-014: `replay_report` input is future-gated. The accepted implementation MUST reject or forbid `replay_deterministic` unless replay evidence directly satisfies `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

OVCL-REQ-015: `text_identity_report` input is future-gated. The accepted implementation MUST reject or forbid `text_deterministic` unless byte identity or declared output-hash identity is explicitly in scope and proven for the same compare scope.

OVCL-REQ-016: The verifier MUST normalize all output paths to workspace-relative or repo-relative form when possible. Absolute paths may appear only when they were explicit input locators and MUST NOT become proof authority.

OVCL-REQ-017: The verifier MUST ignore `diff_ledger` entries when evaluating evidence digests or stable report signatures.

OVCL-REQ-018: If a source `trusted_run_witness_report.v1` does not yet expose `claim_status`, the offline verifier MUST derive output `claim_status` from `observed_result`, `claim_tier`, and `missing_evidence` without treating the missing source field as proof of success.

## Output Requirements

OVCL-REQ-020: The verifier MUST emit stable JSON with `schema_version=offline_trusted_run_verifier.v1`.

OVCL-REQ-021: The verifier output MUST include:

1. `schema_version`
2. `verified_at_utc`
3. `proof_kind`
4. `input_mode`
5. `source_schema_version`
6. `input_refs`
7. `record_id`
8. `observed_path`
9. `observed_result`
10. `claim_status`
11. `claim_tier`
12. `allowed_claims`
13. `forbidden_claims`
14. `compare_scope`
15. `operator_surface`
16. `policy_digest`
17. `control_bundle_ref`
18. `evidence_ref`
19. `required_checks`
20. `passed_checks`
21. `failed_checks`
22. `missing_evidence`
23. `basis_digests`
24. `claim_ladder_basis`
25. `side_effect_free_verification`
26. `report_signature_digest`

OVCL-REQ-022: `observed_path` MUST be one of `primary`, `fallback`, `degraded`, or `blocked`.

OVCL-REQ-023: `observed_result` MUST be one of `success`, `failure`, `partial success`, or `environment blocker`.

OVCL-REQ-024: `claim_status` MUST be one of:

1. `allowed`
2. `downgraded`
3. `blocked`

OVCL-REQ-025: `allowed_claims` MUST list every claim tier proven by the input evidence. A failed or structurally invalid input MUST produce an empty list.

OVCL-REQ-026: Each `forbidden_claims` entry MUST include:

1. `claim_tier`
2. `reason_codes`
3. `missing_evidence`
4. `blocking_check_ids`

OVCL-REQ-027: `basis_digests` MUST include every digest used to justify the selected claim, including contract verdict, invariant model, substrate model, must-catch set, replay evidence, and text identity evidence when applicable.

OVCL-REQ-028: `report_signature_digest` MUST be stable across equivalent verifier inputs and MUST exclude `verified_at_utc`, `diff_ledger`, run-specific ids, session-specific paths, and local absolute path prefixes.

OVCL-REQ-029: A human-facing summary generated from verifier output MUST name the claim tier, claim status, compare scope, and forbidden higher claims.

## Claim Ladder Requirements

OVCL-REQ-030: The verifier MUST assign the highest truthful claim tier allowed by evidence for the first slice and MUST downgrade when required evidence is missing.

OVCL-REQ-031: The verifier MUST evaluate claim tiers against this evidence matrix:

| Claim tier | Required evidence | Downgrade or block when absent |
|---|---|---|
| `non_deterministic_lab_only` | One internally valid bundle or one successful single report with captured control surface, policy identity, compare scope, operator surface, final truth, effect evidence, invariant model, substrate model, and side-effect-free verification. | If minimum lab evidence fails, set `claim_status=blocked` and `allowed_claims=[]`. |
| `verdict_deterministic` | At least two successful verifier reports or one campaign report proving stable contract verdict signature, invariant model signature, substrate signature, must-catch outcome set, compare scope, operator surface, and side-effect-free verification. | Downgrade to `non_deterministic_lab_only` when the single-run evidence remains valid; otherwise block. |
| `replay_deterministic` | All evidence required by `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` for governed replay on the named operator surface, including replay artifact, successful comparison, captured or linked control bundle, and no contradiction with the claim. | Forbid `replay_deterministic` and use the highest lower proven tier. |
| `text_deterministic` | All evidence required for `verdict_deterministic` or `replay_deterministic`, plus byte-identical output or identical declared output hash on the same compare scope. | Forbid `text_deterministic` and use the highest lower proven tier. |

OVCL-REQ-032: `non_deterministic_lab_only` is allowed when a single bundle or report is internally valid but repeat, replay, and text identity evidence are not proven.

OVCL-REQ-033: `verdict_deterministic` is allowed only when repeated verifier evidence proves stable contract verdict, invariant model, substrate model, and must-catch signatures on the same compare scope and operator surface.

OVCL-REQ-034: `replay_deterministic` is allowed only when replay evidence satisfies `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

OVCL-REQ-035: `text_deterministic` is allowed only when byte identity or output-hash identity is explicitly in scope and proven for the same compare scope.

OVCL-REQ-036: The verifier MUST NOT upgrade a claim because generated text appears semantically good.

OVCL-REQ-037: The verifier MUST report forbidden higher claims whenever evidence is insufficient.

OVCL-REQ-038: The first accepted implementation MUST support `non_deterministic_lab_only` and `verdict_deterministic` as allowed claims, and MUST support `replay_deterministic` and `text_deterministic` as forbidden future-gated claims unless explicit evidence schemas are added in the same accepted implementation.

## Forbidden Claim Mapping

OVCL-REQ-040: The verifier MUST use these minimum forbidden-claim mappings:

| Reason code | Forbidden claim | Meaning |
|---|---|---|
| `repeat_evidence_missing` | `verdict_deterministic` | Fewer than two successful reports and no campaign stability proof. |
| `verdict_signature_not_stable` | `verdict_deterministic` | Contract verdict signatures drift across successful reports. |
| `invariant_model_signature_not_stable` | `verdict_deterministic` | Invariant model signatures drift across successful reports. |
| `substrate_signature_not_stable` | `verdict_deterministic` | Substrate signatures drift across successful reports. |
| `must_catch_outcomes_not_stable` | `verdict_deterministic` | Must-catch outcome set drifts across successful reports. |
| `verifier_side_effect_absence_not_mechanically_proven` | `verdict_deterministic` | Side-effect-free verification is missing or false. |
| `compare_scope_mismatch` | all higher claims | Evidence does not share the declared compare scope. |
| `operator_surface_mismatch` | all higher claims | Evidence does not share the declared operator surface. |
| `replay_evidence_missing` | `replay_deterministic` | No governed replay artifact is present. |
| `replay_compare_scope_mismatch` | `replay_deterministic` | Replay evidence is not for the declared compare scope. |
| `replay_result_not_stable` | `replay_deterministic` | Replay comparison fails or contradicts the claim. |
| `text_identity_evidence_missing` | `text_deterministic` | No byte/hash identity evidence is present. |
| `text_compare_scope_mismatch` | `text_deterministic` | Text identity evidence is not for the declared compare scope. |
| `text_hash_not_stable` | `text_deterministic` | Declared output bytes or hashes drift. |

OVCL-REQ-041: Forbidden-claim reasons MUST be machine-readable and stable enough for tests to assert.

OVCL-REQ-042: The verifier MAY include human-facing explanation text, but explanation text MUST NOT be the only record of a forbidden claim.

## Failure Semantics

OVCL-REQ-050: Missing required authority evidence MUST fail closed or downgrade the claim tier.

OVCL-REQ-051: Record id drift across bundle, report, contract verdict, invariant model, substrate model, or campaign report MUST fail closed.

OVCL-REQ-052: Missing final truth MUST fail verification.

OVCL-REQ-053: Approval continuation not bound to the declared checkpoint and run MUST fail verification.

OVCL-REQ-054: Missing or contradicted effect evidence MUST fail verification.

OVCL-REQ-055: Replay or compare evidence required for a requested or reported claim but absent MUST produce a lower truthful claim tier and a forbidden-claim entry.

OVCL-REQ-056: Unsupported schema versions MUST fail verification.

OVCL-REQ-057: All failures MUST be machine-readable, not prose-only.

OVCL-REQ-058: Missing evidence for a higher claim MUST NOT hide a valid lower claim when lower-claim evidence is complete.

OVCL-REQ-059: Missing evidence for the minimum lab claim MUST produce `observed_result=failure` and `claim_status=blocked`.

## Negative Proof Matrix

OVCL-REQ-060: The implementation handoff MUST include table-driven negative examples for:

| Corruption id | Input mode | Mutation | Expected result |
|---|---|---|---|
| `OVCL-CORR-001` | any | unsupported or missing source schema | `schema_version_missing_or_unsupported` failure |
| `OVCL-CORR-002` | any | compare scope changed or missing | `compare_scope_mismatch` or `compare_scope_missing_or_unsupported` |
| `OVCL-CORR-003` | any | operator surface changed or missing | `operator_surface_mismatch` or `operator_surface_missing` |
| `OVCL-CORR-004` | bundle/report | governed run id drifts across surfaces | `canonical_run_id_drift` failure |
| `OVCL-CORR-005` | bundle/report | final truth removed | `missing_final_truth` failure |
| `OVCL-CORR-006` | bundle/report | effect evidence removed or contradicted | `missing_effect_evidence` failure |
| `OVCL-CORR-007` | bundle/report | side-effect-free verification missing | `verifier_side_effect_absence_not_mechanically_proven` forbidden claim or blocker |
| `OVCL-CORR-008` | campaign_report | only one successful report | `repeat_evidence_missing` forbidden claim |
| `OVCL-CORR-009` | campaign_report | contract verdict signatures differ | `verdict_signature_not_stable` forbidden claim |
| `OVCL-CORR-010` | campaign_report | invariant signatures differ | `invariant_model_signature_not_stable` forbidden claim |
| `OVCL-CORR-011` | campaign_report | substrate signatures differ | `substrate_signature_not_stable` forbidden claim |
| `OVCL-CORR-012` | campaign_report | must-catch outcome sets differ | `must_catch_outcomes_not_stable` forbidden claim |
| `OVCL-CORR-013` | replay_report | replay evidence missing | `replay_evidence_missing` forbidden claim |
| `OVCL-CORR-014` | replay_report | replay compare scope differs | `replay_compare_scope_mismatch` forbidden claim |
| `OVCL-CORR-015` | text_identity_report | byte/hash identity evidence missing | `text_identity_evidence_missing` forbidden claim |
| `OVCL-CORR-016` | text_identity_report | output hash differs | `text_hash_not_stable` forbidden claim |

OVCL-REQ-061: Mock-heavy proof MUST NOT be presented as runtime truth.

OVCL-REQ-062: Live proof for the current slice SHOULD remain the ProductFlow Trusted Run Witness campaign unless the user changes the compare scope.

OVCL-REQ-063: Negative examples MAY be generated from minimal valid payloads rather than stored fixtures, but every corruption id MUST be individually asserted.

## Positive Proof Requirements

OVCL-REQ-070: The implementation handoff MUST include one positive single-bundle or single-report example that remains `non_deterministic_lab_only`.

OVCL-REQ-071: The implementation handoff MUST include one positive campaign example that reaches `verdict_deterministic`.

OVCL-REQ-072: The implementation handoff MUST include one requested `replay_deterministic` example that is forbidden because replay evidence is missing.

OVCL-REQ-073: The implementation handoff MUST include one requested `text_deterministic` example that is forbidden because byte/hash identity evidence is missing.

OVCL-REQ-074: Proof reports MUST record observed path as `primary`, `fallback`, `degraded`, or `blocked`, and observed result as `success`, `failure`, `partial success`, or `environment blocker`.

## Durable Spec Decision

OVCL-REQ-080: If these requirements are accepted, durable verifier authority SHOULD be extracted as `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md` before implementation.

OVCL-REQ-081: The extracted spec MUST reference the Trusted Run Witness, Trusted Run Invariants, Control Plane Witness Substrate, and Determinism Gate Policy specs instead of duplicating their full contents.

OVCL-REQ-082: If implementation changes verifier output fields, canonical commands, output paths, or claim surfaces, `CURRENT_AUTHORITY.md` MUST be updated in the same change.

OVCL-REQ-083: The requirements lane MUST remain active until the user accepts these requirements, asks for implementation, or retires the lane.

## Implementation Handoff Requirements

The accepted implementation plan MUST include:

1. durable spec extraction to `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
2. a separate offline claim-evaluator command unless the accepted spec explicitly chooses to extend an existing script
3. stable output path `benchmarks/results/proof/offline_trusted_run_verifier.json`
4. contract tests for bundle, single-report, and campaign-report inputs
5. negative proof matrix tests for every `OVCL-CORR-*` id
6. one live ProductFlow Trusted Run Witness campaign proof for `verdict_deterministic`
7. a same-change update to `CURRENT_AUTHORITY.md` if the implementation creates a new canonical command or output path

## Acceptance State

These requirements are complete enough for user acceptance because they specify:

1. final verifier boundary
2. final supported input modes
3. final verifier output schema requirements
4. final claim ladder rules
5. final forbidden claim mapping
6. final failure semantics
7. positive and negative proof requirements
8. durable spec extraction decision

This requirements lane was accepted by the user's `continue` instruction on 2026-04-18 and moved into implementation under `docs/projects/archive/Proof/OVCL04182026-IMPLEMENTATION-CLOSEOUT/OFFLINE_VERIFIER_AND_CLAIM_LADDER_IMPLEMENTATION_PLAN.md`.
