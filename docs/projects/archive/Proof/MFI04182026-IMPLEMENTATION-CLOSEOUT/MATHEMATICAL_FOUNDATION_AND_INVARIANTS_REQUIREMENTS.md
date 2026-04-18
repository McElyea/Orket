# Mathematical Foundation And Invariants Requirements

Last updated: 2026-04-18
Status: Archived accepted requirements draft
Owner: Orket Core

Canonical plan archive: `docs/projects/archive/Proof/MFI04182026-IMPLEMENTATION-CLOSEOUT/MATHEMATICAL_FOUNDATION_AND_INVARIANTS_REQUIREMENTS_PLAN.md`
Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/03_MATHEMATICAL_FOUNDATION_AND_INVARIANTS.md`
Primary dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`

## Purpose

Define the bounded mathematical foundation for Orket's trusted-run witness surface.

The first formal claim is:

```text
If a side-effect-free verifier accepts a trusted-run witness bundle
for compare_scope = trusted_run_productflow_write_file_v1,
then the recorded trace satisfies the declared trusted-run invariants
for that compare scope.
```

This is not a proof that Orket as a whole is mathematically correct. It is a requirements draft for a small model that makes false trusted-run success harder to ship.

## Resolved Requirements Decisions

1. The first model MUST use both a finite state-machine table and lightweight rule notation.
2. Stable requirement ids use `MFI-REQ-###`.
3. Stable invariant ids use `TRI-INV-###`.
4. Implementation proof MUST include both property-style trace coverage and serialized witness corruption coverage unless an implementation plan explicitly scopes one out with a blocker.
5. Existing Trusted Run Witness v1 checks MAY be mapped to invariants, but incomplete mappings MUST be marked as missing-proof blockers.
6. Durable invariant authority, once accepted, MUST be extracted to `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md` before implementation work begins.

## Scope Requirements

MFI-REQ-001: The first formal model MUST be scoped to `trusted_run_productflow_write_file_v1`.

MFI-REQ-002: The first formal model MUST use `trusted_run.witness_bundle.v1`, `trusted_run_contract_verdict.v1`, and `trusted_run_witness_report.v1` as the observed artifact surfaces.

MFI-REQ-003: The model MUST prove properties of recorded witness evidence, not semantic quality of model-generated text.

MFI-REQ-004: The model MUST NOT claim full formal verification of Orket, Python execution, LLM behavior, filesystem behavior, database behavior, or all ControlPlane paths.

MFI-REQ-005: The model MUST preserve the distinction between:

1. runtime authority records
2. witness-bundle evidence
3. verifier reports
4. campaign reports
5. human-facing summaries

MFI-REQ-006: Supporting projections such as run summaries, Packet 1/2 blocks, review packages, and graphs MAY be model inputs only when they are explicitly marked as projections and never replace required authority records.

MFI-REQ-007: The requirements MUST treat missing evidence as a first-class verifier result, not as implied success.

## Formal Model Requirements

MFI-REQ-010: The formal model MUST be smaller than the implementation. It MUST model only the trusted-run witness facts required to decide the declared compare scope.

MFI-REQ-011: The model state MUST include these record families:

1. `Run`
2. `Attempt`
3. `Step`
4. `Checkpoint`
5. `ApprovalRequest`
6. `OperatorAction`
7. `Reservation`
8. `Lease`
9. `Resource`
10. `EffectJournal`
11. `FinalTruth`
12. `ObservedArtifact`
13. `ContractVerdict`
14. `WitnessBundle`
15. `VerifierReport`
16. `CampaignReport`

MFI-REQ-012: The model MUST explicitly identify which fields from each record family are in scope.

MFI-REQ-013: The model MUST explicitly identify which implementation details are out of scope. At minimum, out-of-scope details include actual SQL schemas, Pydantic validation internals, wall-clock timestamp values, generated UUID contents, model text generation, and filesystem write mechanics.

MFI-REQ-014: The model MUST define these transition classes:

| Transition | Required preconditions | Required result |
|---|---|---|
| `admit_run` | governed input, policy snapshot, configuration snapshot | one non-empty governed `run_id` |
| `start_attempt` | known run, no contradictory terminal final truth | one current attempt for the modeled run |
| `publish_checkpoint` | known run and attempt, policy digest | accepted checkpoint or fail-closed blocker |
| `request_approval` | known run, approval-required effect | pending approval request bound to the run |
| `resolve_approval` | pending approval request, operator action | approved continuation or terminal/blocking denial |
| `establish_resource_authority` | known namespace scope | reservation and lease/resource evidence or fail-closed blocker |
| `publish_effect` | known run, attempt, step, authorization basis | effect-journal entry or fail-closed blocker |
| `publish_final_truth` | known run, sufficient evidence | terminal final truth or explicit non-success truth |
| `build_witness_bundle` | required authority records | serialized bundle with path/digest refs |
| `verify_bundle` | serialized bundle only | side-effect-free verifier report |
| `compare_campaign` | at least two verifier reports | campaign claim tier or lower-tier blocker |

MFI-REQ-015: Every modeled transition MUST have fail-closed semantics for missing required preconditions.

MFI-REQ-016: The model MUST forbid success-shaped outputs from unsupported lifecycle states.

MFI-REQ-017: The model MUST define a deterministic ordering relation for the modeled trace. Timestamps MAY be evidence metadata but MUST NOT be used as the primary ordering rule.

MFI-REQ-018: The model MUST define equality for verdict signatures so two equivalent successful runs can be compared without depending on run-specific identifiers or timestamps.

## Trusted-Run Invariants

TRI-INV-001: A witness bundle accepted for the first slice MUST have `schema_version=trusted_run.witness_bundle.v1`.

TRI-INV-002: An accepted witness bundle MUST have `compare_scope=trusted_run_productflow_write_file_v1`.

TRI-INV-003: An accepted witness bundle MUST have `operator_surface=trusted_run_witness_report.v1`.

TRI-INV-004: An accepted witness bundle MUST carry a non-empty canonical governed turn-tool `run_id`.

TRI-INV-005: `session_id` and artifact-root locators MUST NOT substitute for the canonical governed `run_id`.

TRI-INV-006: The canonical `run_id` MUST align across run authority, approval request, checkpoint, final truth, and verifier report evidence.

TRI-INV-007: Policy snapshot, configuration snapshot, policy digest, and control-bundle reference MUST be present before any trusted-run success claim.

TRI-INV-008: Required artifact references MUST include at least the run summary and bounded output artifact, and each reference MUST carry path plus digest or equivalent integrity evidence.

TRI-INV-009: Governed input evidence MUST identify the admitted ProductFlow epic, issue, builder seat, and approval-required tool seam.

TRI-INV-010: A successful accepted bundle MUST include run, attempt, and step evidence sufficient to explain the observed execution path.

TRI-INV-011: Approval continuation MUST bind the approval request to the same governed run.

TRI-INV-012: Approval continuation MUST include an operator action or approval-resolution record.

TRI-INV-013: Approval continuation MUST bind to an accepted checkpoint for the same governed run.

TRI-INV-014: A namespace-scoped trusted-run effect MUST include resource authority evidence.

TRI-INV-015: A namespace-scoped trusted-run effect MUST include reservation and lease evidence.

TRI-INV-016: A lease used for trusted-run success MUST be traceable to a reservation or explicit missing-proof blocker.

TRI-INV-017: The latest resource authority MUST not contradict the lease authority used for the trusted-run effect.

TRI-INV-018: A successful accepted bundle MUST include effect-journal evidence for the in-scope local mutation.

TRI-INV-019: Effect-journal evidence MUST identify or imply known run, attempt, step, authorization basis, intended target, observed result, and uncertainty classification.

TRI-INV-020: A non-initial effect-journal entry MUST link to a prior effect-journal entry or produce an explicit missing-proof blocker.

TRI-INV-021: The bounded output path MUST equal `agent_output/productflow/approved.txt`.

TRI-INV-022: The normalized bounded output content MUST equal `approved`.

TRI-INV-023: The terminal issue status MUST equal `done`.

TRI-INV-024: Final truth MUST be present before any trusted-run success claim.

TRI-INV-025: Successful final truth MUST have result class `success` and evidence sufficiency `evidence_sufficient`.

TRI-INV-026: A terminal run MUST have one terminal final-truth authority for the modeled run or produce an explicit missing-proof blocker.

TRI-INV-027: `trusted_run_contract_verdict.v1` MUST be present before the verifier reports bundle success.

TRI-INV-028: The verifier MUST recompute the contract verdict and fail closed if the included verdict digest drifts.

TRI-INV-029: A single accepted bundle MUST remain `non_deterministic_lab_only`.

TRI-INV-030: `verdict_deterministic` MUST require at least two successful verifier reports or a campaign artifact showing stable verdict signature and stable must-catch outcome set.

TRI-INV-031: The verifier MUST be side-effect free with respect to workflow state. If this cannot be proven mechanically, the report MUST expose a missing-proof blocker.

TRI-INV-032: The campaign MUST NOT claim `replay_deterministic` unless replay evidence satisfies `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

TRI-INV-033: The campaign MUST NOT claim `text_deterministic` unless byte or hash identity is explicitly in scope and proven on the same compare scope.

## Invariant To Current Check Mapping

| Invariant | Current Trusted Run Witness v1 support | Requirement status |
|---|---|---|
| TRI-INV-001 | `schema` check in `build_contract_verdict` | covered |
| TRI-INV-002 | `compare_scope` check | covered |
| TRI-INV-003 | `operator_surface` check | covered |
| TRI-INV-004 | `run_id_lineage` requires non-empty run id | covered |
| TRI-INV-005 | `run_id_lineage` requires `session_id` to appear in run id | partial; needs explicit locator-not-authority rule |
| TRI-INV-006 | `run_id_lineage`, `approval_request`, `checkpoint`, `final_truth` checks | covered |
| TRI-INV-007 | `policy_configuration` check | covered |
| TRI-INV-008 | `artifact_refs` check | covered |
| TRI-INV-009 | `governed_input` check | covered |
| TRI-INV-010 | run evidence is checked; step evidence is not independently required | missing-proof blocker: `step_lineage_not_independently_verified` |
| TRI-INV-011 | `approval_request` check | covered |
| TRI-INV-012 | `approval_resolution` check | covered |
| TRI-INV-013 | `checkpoint` check | covered |
| TRI-INV-014 | `resource_and_lease` checks resource id | covered for first slice |
| TRI-INV-015 | `resource_and_lease` checks reservation and lease refs | partial; refs are checked, records are not fully modeled |
| TRI-INV-016 | no explicit lease-to-reservation source check | missing-proof blocker: `lease_source_reservation_not_verified` |
| TRI-INV-017 | no explicit resource-versus-lease contradiction check | missing-proof blocker: `resource_lease_consistency_not_verified` |
| TRI-INV-018 | `effect_journal` requires at least two entries | covered for presence |
| TRI-INV-019 | current check verifies count and no residual uncertainty only | partial; needs target and authorization details |
| TRI-INV-020 | no prior-entry chain check | missing-proof blocker: `effect_prior_chain_not_verified` |
| TRI-INV-021 | `output_path` check | covered |
| TRI-INV-022 | `output_content` check | covered |
| TRI-INV-023 | `issue_status` check | covered |
| TRI-INV-024 | `final_truth` check | covered |
| TRI-INV-025 | `final_truth` checks result and evidence sufficiency | covered |
| TRI-INV-026 | no cardinality check for exactly one terminal final truth | missing-proof blocker: `final_truth_cardinality_not_verified` |
| TRI-INV-027 | `verify_witness_bundle_payload` fails on missing verdict | covered |
| TRI-INV-028 | included/recomputed verdict digest comparison | covered |
| TRI-INV-029 | single-bundle verifier returns `non_deterministic_lab_only` | covered |
| TRI-INV-030 | campaign requires two successes, one verdict digest, one must-catch set | covered |
| TRI-INV-031 | report marks side-effect-free verification, but no mutation-diff proof exists | missing-proof blocker: `verifier_side_effect_absence_not_mechanically_proven` |
| TRI-INV-032 | no replay deterministic claim in current surface | covered |
| TRI-INV-033 | no text deterministic claim in current surface | covered |

## Negative Corruption Matrix

The implementation handoff MUST include corruptions for every covered invariant and explicit blocker tests for every missing-proof invariant.

| Corruption id | Mutation | Expected result |
|---|---|---|
| MFI-CORR-001 | remove `schema_version` or change it to an unsupported value | verifier failure: `schema_version_missing_or_unsupported` |
| MFI-CORR-002 | change `compare_scope` | verifier failure: `compare_scope_missing_or_unsupported` |
| MFI-CORR-003 | change `operator_surface` | verifier failure: `operator_surface_missing` |
| MFI-CORR-004 | remove top-level `run_id` | verifier failure: `canonical_run_id_drift` |
| MFI-CORR-005 | mutate `authority_lineage.run.run_id` | verifier failure: `canonical_run_id_drift` |
| MFI-CORR-006 | mutate `authority_lineage.approval_request.control_plane_target_ref` | verifier failure: `approval_request_missing_or_drifted` |
| MFI-CORR-007 | mutate checkpoint id to a different run | verifier failure: `checkpoint_missing_or_drifted` |
| MFI-CORR-008 | remove `policy_digest` | verifier failure: `policy_or_configuration_missing` |
| MFI-CORR-009 | remove `configuration_snapshot_ref` | verifier failure: `policy_or_configuration_missing` |
| MFI-CORR-010 | remove run-summary artifact digest | verifier failure: `artifact_ref_missing` |
| MFI-CORR-011 | remove output artifact digest | verifier failure: `artifact_ref_missing` |
| MFI-CORR-012 | change governed epic, issue, or seat | verifier failure: `governed_input_missing` |
| MFI-CORR-013 | remove approval resolution | verifier failure: `missing_approval_resolution` |
| MFI-CORR-014 | change operator action result away from approved | verifier failure: `missing_approval_resolution` |
| MFI-CORR-015 | remove reservation or lease refs | verifier failure: `resource_or_lease_evidence_missing` |
| MFI-CORR-016 | change resource id away from `namespace:issue:PF-WRITE-1` | verifier failure: `resource_or_lease_evidence_missing` |
| MFI-CORR-017 | remove effect-journal evidence | verifier failure: `missing_effect_evidence` |
| MFI-CORR-018 | lower effect entry count below two | verifier failure: `missing_effect_evidence` |
| MFI-CORR-019 | change effect uncertainty away from `no_residual_uncertainty` | verifier failure: `missing_effect_evidence` |
| MFI-CORR-020 | change output path | verifier failure: `missing_output_artifact` |
| MFI-CORR-021 | change output content | verifier failure: `wrong_output_content` |
| MFI-CORR-022 | change issue status away from `done` | verifier failure: `wrong_terminal_issue_status` |
| MFI-CORR-023 | remove final truth | verifier failure: `missing_final_truth` |
| MFI-CORR-024 | change final truth result away from `success` | verifier failure: `missing_final_truth` |
| MFI-CORR-025 | remove contract verdict | verifier failure: `contract_verdict_missing` |
| MFI-CORR-026 | mutate included contract verdict digest | verifier failure: `contract_verdict_drift` |
| MFI-CORR-027 | provide only one successful verifier report to campaign | campaign fallback: `non_deterministic_lab_only`, blocker `repeat_evidence_missing` |
| MFI-CORR-028 | provide two successful reports with different verdict signatures | campaign fallback: `non_deterministic_lab_only`, blocker `verdict_signature_not_stable` |
| MFI-CORR-029 | provide a bundle with valid `session_id` but mismatched governed run resolver witness | verifier failure: `canonical_run_id_drift` or explicit resolver-drift failure |
| MFI-CORR-030 | remove side-effect-free verification proof once implemented | verifier or campaign blocker: `verifier_side_effect_absence_not_mechanically_proven` |

## Proof Stack Requirements

MFI-REQ-030: The implementation handoff MUST include model-level tests for legal traces.

MFI-REQ-031: The implementation handoff MUST include model-level tests for illegal traces.

MFI-REQ-032: The implementation handoff MUST include serialized witness-bundle corruption tests for every corruption listed in this draft or explain why the corruption belongs to a later slice.

MFI-REQ-033: Property-style trace generation MUST not be treated as live proof. It is contract or structural proof.

MFI-REQ-034: Live proof for the first slice MUST remain the ProductFlow trusted-run campaign unless the user explicitly changes the compare scope.

MFI-REQ-035: Mock-heavy proof MUST NOT be presented as runtime truth.

MFI-REQ-036: A proof report MUST record proof type, observed path, observed result, claim tier, compare scope, operator surface, and remaining blockers or drift.

MFI-REQ-037: Missing-proof blockers MUST remain visible in proof output until implemented.

## Durable Spec Extraction Requirements

MFI-REQ-040: If these requirements are accepted, durable contract material MUST be extracted into `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md` before implementation begins.

MFI-REQ-041: `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md` MUST not duplicate the full Trusted Run Witness bundle schema. It MUST reference `docs/specs/TRUSTED_RUN_WITNESS_V1.md` for bundle shape and define only the model, invariants, proof obligations, and fail-closed semantics.

MFI-REQ-042: If implementation changes the trusted-run bundle schema or canonical verifier report fields, `docs/specs/TRUSTED_RUN_WITNESS_V1.md` MUST be updated in the same change.

MFI-REQ-043: `CURRENT_AUTHORITY.md` MUST be updated only when implementation changes actual behavior, canonical paths, source-of-truth specs, or claim surfaces.

## Claim-Tier Requirements

MFI-REQ-050: The requirements MUST preserve `verdict_deterministic` as the maximum supported claim tier for the current ProductFlow trusted-run witness campaign.

MFI-REQ-051: The requirements MUST preserve `non_deterministic_lab_only` for any single-bundle witness.

MFI-REQ-052: The requirements MUST NOT permit `replay_deterministic` without replay evidence under `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

MFI-REQ-053: The requirements MUST NOT permit `text_deterministic` without byte or output-hash identity evidence on the same compare scope.

MFI-REQ-054: Any human-facing statement derived from this lane MUST name the compare scope and claim tier.

## Acceptance Proof Requirements

Before this requirements lane can close as accepted, it MUST provide:

1. a final accepted invariant catalog
2. a final accepted state-machine transition table
3. a final accepted invariant-to-check mapping
4. a final accepted negative corruption matrix
5. explicit missing-proof blockers for incomplete invariant coverage
6. a durable spec extraction decision
7. remaining implementation decisions

Before a later implementation lane can close, it MUST provide:

1. contract or structural proof for model-valid traces
2. contract or structural proof for model-invalid traces
3. corruption tests for covered invariants
4. blocker tests or proof-output checks for missing-proof invariants
5. side-effect-free verification proof or explicit blocker
6. live ProductFlow campaign proof if claim tier remains `verdict_deterministic`
7. docs hygiene proof

## Remaining Implementation Decisions

1. exact file layout for future model helper code
2. whether property-style trace generation uses Hypothesis or deterministic table-driven generation
3. whether corruption fixtures are generated dynamically or stored as explicit JSON examples
4. exact schema for missing-proof blockers in verifier and campaign output
5. whether `trusted_run_witness_contract.py` absorbs the invariant model or delegates to a separate proof-model module
6. whether effect-journal prior-chain proof is pulled from existing bundle fields or requires bundle schema expansion
7. whether resource-versus-lease contradiction proof is expressible from current witness evidence or requires additional authority fields
