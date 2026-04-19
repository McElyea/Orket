# Trusted Run Invariants v1

Last updated: 2026-04-18
Status: Active contract
Owner: Orket Core

This spec defines the bounded invariant model for admitted Trusted Run Witness slices.

The claim is deliberately small:

```text
If the side-effect-free verifier accepts a witness bundle for an admitted
Trusted Run compare scope, then the serialized bundle evidence satisfies the
matching Trusted Run Invariants v1 model.
```

This is not a formal proof of Orket, Python, model output semantics, filesystem behavior, database behavior, or every ControlPlane path. It is a fail-closed model over recorded trusted-run evidence.

## Relationship To Trusted Run Witness v1

This contract depends on `docs/specs/TRUSTED_RUN_WITNESS_V1.md` for the witness bundle schema, verifier report surface, canonical artifact paths, and claim tiers.

This contract adds:

1. the finite trusted-run model boundary
2. the transition classes the verifier reasons about
3. stable invariant ids
4. fail-closed evidence requirements for missing or contradictory evidence
5. the invariant signature required by campaign comparison

It does not replace `trusted_run_contract_verdict.v1`; it tightens verifier acceptance by requiring both the recomputed contract verdict and the invariant model to pass.

## Model Scope

The first ProductFlow model is scoped to:

1. compare scope: `trusted_run_productflow_write_file_v1`
2. witness bundle schema: `trusted_run.witness_bundle.v1`
3. contract verdict surface: `trusted_run_contract_verdict.v1`
4. verifier report surface: `trusted_run_witness_report.v1`
5. bounded output path: `agent_output/productflow/approved.txt`
6. normalized output content: `approved`
7. terminal issue status: `done`

The First Useful Workflow Slice model is scoped to:

1. compare scope: `trusted_repo_config_change_v1`
2. witness bundle schema: `trusted_run.witness_bundle.v1`
3. contract verdict surface: `trusted_repo_change_contract_verdict.v1`
4. validator surface: `trusted_repo_config_validator.v1`
5. verifier report surface: `trusted_run_witness_report.v1`
6. bounded output path: `repo/config/trusted-change.json`
7. expected config schema: `trusted_repo_change.config.v1`

The Terraform plan decision model is scoped to:

1. compare scope: `trusted_terraform_plan_decision_v1`
2. witness bundle schema: `trusted_run.witness_bundle.v1`
3. contract verdict surface: `trusted_terraform_plan_decision_contract_verdict.v1`
4. validator surface: `trusted_terraform_plan_decision_validator.v1`
5. verifier report surface: `trusted_run_witness_report.v1`
6. bounded decision artifact: Terraform plan reviewer `final_review.json`

The ProductFlow model uses `TRI-INV-*` invariant ids. The First Useful Workflow Slice model uses `TRC-INV-*` invariant ids so the useful workflow can add validator-specific checks without relabeling ProductFlow invariants. The Terraform plan decision model uses `TTPD-INV-*` invariant ids so Terraform-specific review-decision and audit-publication checks stay scope-local.

The model observes these record families through serialized witness evidence:

| Family | In-scope fields |
|---|---|
| Run | `run_id`, `current_attempt_id`, `current_attempt_state`, `policy_snapshot_id`, `configuration_snapshot_id`, `final_truth_record_id` |
| Attempt | `current_attempt_id` as carried by run evidence |
| Step | `step_count`, `latest_step_id`, `latest_output_ref`, `latest_resources_touched` |
| Checkpoint | `checkpoint_id`, `acceptance_outcome`, `policy_digest`, `acceptance_dependent_reservation_refs`, `acceptance_dependent_lease_refs` |
| ApprovalRequest | `approval_id`, `status`, `reason`, `control_plane_target_ref`, `payload_digest` |
| OperatorAction | `result`, `affected_resource_refs`, `precondition_basis_ref` |
| Reservation | `reservation_id`, `status`, `resource_id`, `reservation_kind` |
| Lease | lease refs from checkpoint and explicit lease record fields when present |
| Resource | `resource_id`, `provenance_ref`, `namespace_scope`, `current_observed_state` |
| EffectJournal | `effect_entry_count`, `latest_step_id`, `latest_authorization_basis_ref`, `latest_intended_target_ref`, `latest_observed_result_ref`, `latest_uncertainty_classification`, `latest_prior_journal_entry_id`, `latest_prior_entry_digest` |
| FinalTruth | `final_truth_record_id`, `result_class`, `evidence_sufficiency_classification` |
| ObservedArtifact | output path, normalized content, issue status, content digest |
| ContractVerdict | schema, recomputed verdict, digest, failures, must-catch outcomes |
| WitnessBundle | schema, bundle id, run id, session id, compare scope, operator surface, claim tier, policy refs, artifact refs |
| VerifierReport | result, claim tier, contract verdict, invariant model, missing evidence |
| CampaignReport | run count, successful verifier count, verdict signature set, invariant signature set, claim tier |

Out of scope details include SQL schema design, Pydantic internals, wall-clock timestamp values, generated UUID contents, model-generated text semantics, filesystem write mechanics, and broader replay determinism.

## Transition Model

The verifier models transition classes, not implementation call stacks.

| Transition | Required preconditions | Required result |
|---|---|---|
| `admit_run` | governed ProductFlow epic, issue, builder seat, policy snapshot, configuration snapshot | one non-empty governed turn-tool `run_id` |
| `start_attempt` | known run, no contradictory terminal final truth | one current attempt for the modeled run |
| `publish_checkpoint` | known run, current attempt, policy digest | accepted checkpoint or fail-closed evidence failure |
| `request_approval` | known run, approval-required effect | pending or approved approval request bound to the run |
| `resolve_approval` | approval request and operator action | approved continuation or fail-closed evidence failure |
| `establish_resource_authority` | known namespace scope | reservation and lease/resource evidence or fail-closed evidence failure |
| `publish_effect` | known run, attempt, step, authorization basis | effect-journal entry or fail-closed evidence failure |
| `publish_final_truth` | known run, sufficient evidence | terminal final truth or explicit non-success truth |
| `build_witness_bundle` | required authority records | serialized bundle with authority, artifact path, and digest refs |
| `verify_bundle` | serialized bundle only | side-effect-free verifier report |
| `compare_campaign` | at least two verifier reports | `verdict_deterministic` or lower-tier blocker |

Every transition is fail-closed. Missing preconditions cannot produce success-shaped verifier output.

Ordering is evidence-based. The primary order relation is:

```text
run -> attempt -> checkpoint/approval -> resource authority -> step/effect -> final truth -> bundle -> verifier report -> campaign
```

Timestamps may be metadata. They are not the primary ordering rule.

## Invariants

TRI-INV-001: An accepted bundle MUST have `schema_version=trusted_run.witness_bundle.v1`.

TRI-INV-002: An accepted bundle MUST have `compare_scope=trusted_run_productflow_write_file_v1`.

TRI-INV-003: An accepted bundle MUST have `operator_surface=trusted_run_witness_report.v1`.

TRI-INV-004: An accepted bundle MUST carry a non-empty canonical governed turn-tool `run_id`.

TRI-INV-005: `session_id` and artifact roots MUST remain locators and MUST NOT substitute for the governed `run_id`.

TRI-INV-006: The governed `run_id` MUST align across run authority, approval request, checkpoint, final truth, and verifier evidence.

TRI-INV-007: Policy snapshot, configuration snapshot, policy digest, and control-bundle reference MUST be present before success.

TRI-INV-008: Required artifact refs MUST include run summary and bounded output artifact, each with path and digest.

TRI-INV-009: Governed input MUST identify ProductFlow epic, issue, builder seat, and approval-required tool seam.

TRI-INV-010: Successful evidence MUST include run, current attempt, and step linkage.

TRI-INV-011: Approval continuation MUST bind the approval request to the same governed run.

TRI-INV-012: Approval continuation MUST include approved operator action evidence.

TRI-INV-013: Approval continuation MUST bind to an accepted checkpoint for the same governed run.

TRI-INV-014: Namespace-scoped trusted-run effects MUST include resource authority evidence.

TRI-INV-015: Namespace-scoped trusted-run effects MUST include reservation and lease evidence.

TRI-INV-016: A lease used for trusted-run success MUST be traceable to reservation evidence.

TRI-INV-017: Latest resource authority MUST not contradict the lease authority used for the trusted-run effect.

TRI-INV-018: Successful evidence MUST include effect-journal evidence for the local mutation.

TRI-INV-019: Effect-journal evidence MUST identify known step, authorization basis, intended target, observed result, and uncertainty classification.

TRI-INV-020: Non-initial effect-journal evidence MUST link to prior effect-journal evidence.

TRI-INV-021: The bounded output path MUST equal `agent_output/productflow/approved.txt`.

TRI-INV-022: The normalized bounded output content MUST equal `approved`.

TRI-INV-023: The terminal issue status MUST equal `done`.

TRI-INV-024: Final truth MUST be present before success.

TRI-INV-025: Successful final truth MUST have result class `success` and evidence sufficiency `evidence_sufficient`.

TRI-INV-026: A terminal run MUST have one terminal final-truth authority for the modeled run.

TRI-INV-027: `trusted_run_contract_verdict.v1` MUST be present before verifier success.

TRI-INV-028: The verifier MUST recompute the contract verdict and fail closed if the included verdict digest drifts.

TRI-INV-029: A single accepted bundle MUST remain `non_deterministic_lab_only`.

TRI-INV-030: `verdict_deterministic` MUST require at least two successful verifier reports with stable verdict and invariant signatures.

TRI-INV-031: Bundle verification MUST be side-effect free with respect to workflow state, with the current structural proof carried by `trusted_run_proof_foundation.v1`.

TRI-INV-032: A campaign MUST NOT claim `replay_deterministic` without replay evidence satisfying `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

TRI-INV-033: A campaign MUST NOT claim `text_deterministic` without byte or hash identity evidence on the same compare scope.

## Missing Evidence And Blockers

The invariant model MUST emit explicit failures or blockers for missing evidence. A missing-proof blocker is allowed only when the implementation cannot check an accepted invariant from the current bundle surface.

As of this contract, the ProductFlow trusted-run bundle surface is expected to close the former blockers for:

1. step lineage
2. lease-to-reservation source evidence
3. resource-versus-lease consistency
4. effect-journal prior-chain evidence
5. final-truth cardinality
6. verifier side-effect absence at bundle-evaluation scope

If a later runtime cannot supply those fields, verifier output must expose the blocker instead of accepting the bundle.

The canonical structural proof artifact for the fixed ProductFlow Workstream 1 target set is `trusted_run_proof_foundation.v1`, written by `python scripts/proof/verify_trusted_run_proof_foundation.py` to `benchmarks/results/proof/trusted_run_proof_foundation.json`.

## Negative Corruption Matrix

The verifier must fail closed for these serialized bundle corruptions:

| Corruption id | Mutation | Expected failure or blocker |
|---|---|---|
| MFI-CORR-001 | remove or change `schema_version` | `schema_version_missing_or_unsupported` |
| MFI-CORR-002 | change `compare_scope` | `compare_scope_missing_or_unsupported` |
| MFI-CORR-003 | change `operator_surface` | `operator_surface_missing` |
| MFI-CORR-004 | remove top-level `run_id` | `canonical_run_id_drift` |
| MFI-CORR-005 | mutate `authority_lineage.run.run_id` | `canonical_run_id_drift` |
| MFI-CORR-006 | mutate approval target ref | `approval_request_missing_or_drifted` |
| MFI-CORR-007 | mutate checkpoint id to a different run | `checkpoint_missing_or_drifted` |
| MFI-CORR-008 | remove `policy_digest` | `policy_or_configuration_missing` |
| MFI-CORR-009 | remove `configuration_snapshot_ref` | `policy_or_configuration_missing` |
| MFI-CORR-010 | remove run-summary artifact digest | `artifact_ref_missing` |
| MFI-CORR-011 | remove output artifact digest | `artifact_ref_missing` |
| MFI-CORR-012 | change governed epic, issue, or seat | `governed_input_missing` |
| MFI-CORR-013 | remove approval resolution | `missing_approval_resolution` |
| MFI-CORR-014 | change operator result away from approved | `missing_approval_resolution` |
| MFI-CORR-015 | remove reservation or lease refs | `resource_or_lease_evidence_missing` |
| MFI-CORR-016 | change resource id away from `namespace:issue:PF-WRITE-1` | `resource_or_lease_evidence_missing` |
| MFI-CORR-017 | remove effect-journal evidence | `missing_effect_evidence` |
| MFI-CORR-018 | lower effect entry count below two | `missing_effect_evidence` |
| MFI-CORR-019 | change effect uncertainty away from `no_residual_uncertainty` | `missing_effect_evidence` |
| MFI-CORR-020 | change output path | `missing_output_artifact` |
| MFI-CORR-021 | change output content | `wrong_output_content` |
| MFI-CORR-022 | change issue status away from `done` | `wrong_terminal_issue_status` |
| MFI-CORR-023 | remove final truth | `missing_final_truth` |
| MFI-CORR-024 | change final truth result away from success | `missing_final_truth` |
| MFI-CORR-025 | remove contract verdict | `contract_verdict_missing` |
| MFI-CORR-026 | mutate included verdict digest | `contract_verdict_drift` |
| MFI-CORR-027 | provide one verifier report to campaign | `repeat_evidence_missing` |
| MFI-CORR-028 | provide two reports with different verdict signatures | `verdict_signature_not_stable` |
| MFI-CORR-029 | provide a valid `session_id` but mismatched run resolver witness | `canonical_run_id_drift` |
| MFI-CORR-030 | remove side-effect-free proof field or invariant-model support | `verifier_side_effect_absence_not_mechanically_proven` |

## Invariant Signature

The invariant signature digest MUST be stable across equivalent successful runs and exclude timestamps, run-specific identifiers, session-specific paths, and generated ids.

Signature material MUST include:

1. invariant model schema version
2. compare scope
3. operator surface
4. expected bounded output path, normalized content, and issue status
5. each invariant id and status
6. campaign-relevant claim-tier guard status
7. missing-proof blockers

`verdict_deterministic` requires a stable contract-verdict signature and a stable invariant signature. For `trusted_repo_config_change_v1` and `trusted_terraform_plan_decision_v1`, campaign promotion also requires a stable validator signature on the scope-local validator surface.
