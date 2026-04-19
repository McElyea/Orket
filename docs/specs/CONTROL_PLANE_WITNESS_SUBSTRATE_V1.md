# Control Plane Witness Substrate v1

Last updated: 2026-04-18
Status: Active contract
Owner: Orket Core

This spec defines how the control plane serves as witness substrate for bounded trusted-run proof.

It does not claim that the whole control plane is universally governed or formally verified. It defines which evidence families may support the first Trusted Run Witness slice and which convenience projections cannot replace authority.

The governing rule is:

```text
No new authority noun without a verifier question it answers.
```

## Scope

The first ProductFlow substrate contract is scoped to:

1. compare scope: `trusted_run_productflow_write_file_v1`
2. witness bundle schema: `trusted_run.witness_bundle.v1`
3. contract verdict surface: `trusted_run_contract_verdict.v1`
4. invariant model surface: `trusted_run_invariant_model.v1`
5. substrate model surface: `control_plane_witness_substrate.v1`
6. verifier report surface: `trusted_run_witness_report.v1`

The First Useful Workflow Slice substrate contract is scoped to:

1. compare scope: `trusted_repo_config_change_v1`
2. witness bundle schema: `trusted_run.witness_bundle.v1`
3. contract verdict surface: `trusted_repo_change_contract_verdict.v1`
4. validator surface: `trusted_repo_config_validator.v1`
5. invariant model surface: `trusted_run_invariant_model.v1`
6. substrate model surface: `control_plane_witness_substrate.v1`
7. verifier report surface: `trusted_run_witness_report.v1`

The Terraform plan decision substrate contract is scoped to:

1. compare scope: `trusted_terraform_plan_decision_v1`
2. witness bundle schema: `trusted_run.witness_bundle.v1`
3. contract verdict surface: `trusted_terraform_plan_decision_contract_verdict.v1`
4. validator surface: `trusted_terraform_plan_decision_validator.v1`
5. invariant model surface: `trusted_run_invariant_model.v1`
6. substrate model surface: `control_plane_witness_substrate.v1`
7. verifier report surface: `trusted_run_witness_report.v1`

For `trusted_repo_config_change_v1` and `trusted_terraform_plan_decision_v1`, `validator_result` is a required authority family. The substrate model must fail closed when the validator is missing, failing, or disconnected from the bounded output artifact.

This spec depends on:

1. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
2. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
3. `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`

It does not duplicate the Trusted Run Witness schema or Trusted Run Invariant catalog.

## Evidence Classifications

Every evidence family used by the first substrate model is classified as one of:

1. `required_authority`
2. `authority_preserving_projection`
3. `optional_supporting_evidence`
4. `projection_only`
5. `forbidden_substitute`
6. `out_of_scope`

`required_authority` means verifier success depends on evidence from that family.

`authority_preserving_projection` means the witness bundle may carry a bounded projection of a source authority record when source identity, path, ref, or digest-equivalent evidence is preserved and the verifier checks the required fields.

`optional_supporting_evidence` may improve human review or later automation but is not required for first-slice verifier success.

`projection_only` may summarize authority but cannot replace required authority.

`forbidden_substitute` must fail closed if used in place of required authority.

`out_of_scope` is outside the first trusted-run substrate claim.

## Record-Family Matrix

| Record family | Classification | First-slice source evidence | Verifier question | Fail-closed condition |
|---|---|---|---|---|
| governed input | `required_authority` | `authority_lineage.governed_input`, `productflow_slice`, approval payload digest | What ProductFlow request was admitted and for which issue and seat? | Missing or drifted input fails as `governed_input_missing`. |
| workload/catalog classification | `optional_supporting_evidence` | governed start-path matrix and ProductFlow workload context | Which governed start path admitted the work? | Not required for current verifier success; later required absence becomes `workload_authority_missing`. |
| resolved policy snapshot | `required_authority` | `policy_snapshot_ref`, `policy_digest`, checkpoint policy digest | Which policy admitted the run and checkpoint? | Missing policy identity fails as `policy_or_configuration_missing`. |
| resolved configuration snapshot | `required_authority` | `configuration_snapshot_ref`, run configuration snapshot id | Which configuration admitted the run? | Missing configuration identity fails as `policy_or_configuration_missing`. |
| run | `required_authority` | `authority_lineage.run` | Which governed run is canonical? | Missing or mismatched run id fails as `canonical_run_id_drift`. |
| attempt | `authority_preserving_projection` | `authority_lineage.run.current_attempt_id` and attempt state | Which attempt was current for the effect? | Missing current attempt identity fails as `step_lineage_missing_or_drifted`. |
| step | `required_authority` | `authority_lineage.step` plus effect-journal step linkage | Which step explains the effect-journal entry? | Missing or contradictory step/effect linkage fails as `step_lineage_missing_or_drifted`. |
| approval request | `required_authority` | approval row fields copied into `authority_lineage.approval_request` | Was an approval-required tool seam requested for this run? | Missing or wrong approval target fails as `approval_request_missing_or_drifted`. |
| operator action | `required_authority` | approval resolution/operator action fields | Did an operator approve the continuation? | Missing or non-approved operator action fails as `missing_approval_resolution`. |
| checkpoint acceptance | `required_authority` | `authority_lineage.checkpoint` | Was continuation allowed from an accepted boundary? | Missing, wrong-run, or non-accepted checkpoint fails as `checkpoint_missing_or_drifted`. |
| reservation | `required_authority` | `authority_lineage.reservation` and checkpoint reservation refs | What authority reserved or held the namespace before effect? | Missing source reservation evidence fails as `lease_source_reservation_not_verified` or `resource_or_lease_evidence_missing`. |
| lease | `authority_preserving_projection` | checkpoint lease refs and resource provenance ref | Which authority owned the namespace at execution? | Missing lease refs fail as `resource_or_lease_evidence_missing`; source mismatch fails as `lease_source_reservation_not_verified`. |
| resource | `required_authority` | `authority_lineage.resource` | Does latest namespace resource authority agree with lease authority? | Missing or contradictory resource authority fails as `resource_or_lease_evidence_missing` or `resource_lease_consistency_not_verified`. |
| effect journal | `required_authority` | `authority_lineage.effect_journal` | What effect was authorized and observed? | Missing effect evidence fails as `missing_effect_evidence`; missing prior chain fails as `effect_prior_chain_not_verified`. |
| final truth | `required_authority` | `authority_lineage.final_truth` and run final truth id | What terminal result was assigned? | Missing final truth fails as `missing_final_truth`; mismatched terminal truth fails as `final_truth_cardinality_not_verified`. |
| bounded output artifact | `required_authority` | `artifact_refs`, `observed_effect` | Does bounded filesystem evidence match the claim? | Missing path or digest fails as `artifact_ref_missing` or `missing_output_artifact`; wrong content fails as `wrong_output_content`. |
| issue state read model | `authority_preserving_projection` | `observed_effect.issue_status` | Did the target issue reach the bounded terminal state? | Wrong terminal state fails as `wrong_terminal_issue_status`; issue status cannot replace final truth. |
| contract verdict | `required_authority` | `contract_verdict` plus recomputation | Did the deterministic verdict pass on the bundle? | Missing or drifted verdict fails as `contract_verdict_missing` or `contract_verdict_drift`. |
| validator result | `required_authority` for `trusted_repo_config_change_v1` | `trusted_repo_config_validator.v1` | Did deterministic config validation pass on the bounded artifact? | Missing validator fails as `missing_validator_result`; failed validation fails as `validator_failed`. |
| invariant model | `required_authority` | verifier-computed `trusted_run_invariant_model.v1` | Do accepted invariants pass on the same bundle evidence? | Missing or failing model blocks verifier success. |
| verifier report | `required_authority` for campaign only | `trusted_run_witness_report.v1` | Did bundle verification succeed without mutating workflow state? | Failed report blocks campaign success; missing side-effect-free proof blocks promotion. |
| campaign report | `optional_supporting_evidence` for bundle verification, `required_authority` for `verdict_deterministic` | campaign verifier output | Are at least two successful reports stable? | One report or unstable signatures keep claim at `non_deterministic_lab_only`. |
| run summary | `projection_only` | `runs/<session_id>/run_summary.json` | Where are supporting run artifacts and resolver witnesses? | Cannot replace run, checkpoint, effect, or final truth authority. |
| review package | `projection_only` | ProductFlow operator review package | What should a human inspect? | Cannot replace required authority. |
| evidence graph | `projection_only` | run evidence graph artifacts | How is evidence visualized? | Graph-only success must fail closed. |
| Packet 1/2 blocks | `projection_only` | packet projections | What is the operator-facing summary? | Cannot replace authority records or verifier reports. |
| model text semantics | `out_of_scope` | model response content | Was generated text semantically good? | Out of scope. |

## Projection Discipline

Projection-only evidence cannot replace required authority, even when it contains success-shaped fields.

The forbidden substitutions are:

1. `session_id` for governed `run_id`
2. artifact root paths for governed `run_id`
3. run-summary status for final truth
4. issue status for final truth
5. approval status for operator action evidence
6. checkpoint existence for accepted checkpoint evidence
7. reservation refs for lease/resource consistency
8. output file content for effect-journal evidence
9. review package for witness bundle
10. campaign report for individual verifier reports
11. graph or Packet projection for source authority

## Failure Vocabulary

The substrate model may reuse existing Trusted Run Witness or Trusted Run Invariant failure names when they precisely describe the failure.

Substrate-specific blocker names are:

| Blocker | Meaning |
|---|---|
| `workload_authority_missing` | A later slice requires catalog workload authority but the bundle does not provide it. |
| `authority_source_ref_missing` | A projection is used as proof evidence without a source ref, path, id, or digest-equivalent marker. |
| `projection_substitute_not_authority` | Projection-only evidence is used where source authority is required. |
| `stale_authority_not_excluded` | The bundle lacks freshness or latest-authority evidence for a requirement that depends on latest state. |
| `substrate_record_family_unclassified` | The bundle or verifier uses a record family not classified by this matrix. |

## Verification Output

Verifier reports SHOULD include a `control_plane_witness_substrate` block with:

1. `schema_version=control_plane_witness_substrate.v1`
2. `compare_scope`
3. `operator_surface`
4. `result`
5. checked record-family rows
6. failures and missing-substrate blockers
7. a stable `substrate_signature_digest`

The substrate signature must be stable across equivalent successful runs and exclude timestamps, run-specific identifiers, session-specific paths, and generated ids.

`verdict_deterministic` requires stable contract-verdict, invariant-model, substrate-model, and must-catch signatures. For `trusted_repo_config_change_v1` and `trusted_terraform_plan_decision_v1`, it also requires a stable validator signature.
