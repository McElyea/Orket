# Control Plane As Witness Substrate Requirements

Last updated: 2026-04-18
Status: Archived accepted requirements draft
Owner: Orket Core

Canonical plan archive: `docs/projects/archive/Proof/CPWS04182026-IMPLEMENTATION-CLOSEOUT/CONTROL_PLANE_AS_WITNESS_SUBSTRATE_REQUIREMENTS_PLAN.md`
Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/02_CONTROL_PLANE_AS_WITNESS_SUBSTRATE.md`
Primary dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Primary dependency: `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`

## Purpose

Define how the control plane should serve as witness substrate for bounded trusted-run proof.

This requirements lane does not claim the whole control plane is a universal proof substrate. It defines which control-plane evidence may support a trusted-run witness bundle, which convenience projections may support review, and which projections are forbidden substitutes for authority.

The first useful claim remains:

```text
For compare_scope=trusted_run_productflow_write_file_v1,
accepted verifier output must be traceable to required authority evidence,
not to read-model convenience surfaces.
```

## Operating Rule

CPWS-REQ-001: The lane MUST follow this rule:

```text
No new authority noun without a verifier question it answers.
```

CPWS-REQ-002: The lane MUST prefer strengthening evidence for an already selected trusted-run compare scope over broadening the control-plane product surface.

CPWS-REQ-003: The lane MUST NOT reopen the archived ControlPlane project or require every runtime path to become governed.

CPWS-REQ-004: The lane MUST preserve the distinction between:

1. durable authority records
2. witness-bundle evidence
3. verifier reports
4. campaign reports
5. authority-preserving projections
6. projection-only summaries
7. human-facing summaries

CPWS-REQ-005: The lane MUST treat missing evidence as explicit verifier failure or blocker output, not implied success.

CPWS-REQ-006: The lane MUST NOT add a required record family unless the accepted requirements name the verifier question that family answers.

## Baseline Requirements

CPWS-REQ-010: The first substrate requirements MUST be scoped to `trusted_run_productflow_write_file_v1`.

CPWS-REQ-011: The baseline trusted-run authority surfaces are `trusted_run.witness_bundle.v1`, `trusted_run_contract_verdict.v1`, `trusted_run_invariant_model.v1`, and `trusted_run_witness_report.v1`.

CPWS-REQ-012: The requirements MUST use `docs/specs/TRUSTED_RUN_WITNESS_V1.md` for witness bundle shape and `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md` for accepted invariant behavior.

CPWS-REQ-013: The requirements MUST NOT duplicate the full invariant catalog. They MUST map control-plane record families to verifier questions.

CPWS-REQ-014: The requirements MUST not treat ProductFlow review packages, run summaries, Packet 1/2 blocks, evidence graphs, or operator-facing summaries as native authority unless a durable authority source is named.

CPWS-REQ-015: The requirements MUST preserve `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md` as the authority for workload start-path classification. This lane may consume that matrix, but it MUST NOT create a parallel workload-authority list.

CPWS-REQ-016: The first slice MAY accept authority-preserving projections inside a witness bundle only when the projection is derived from named control-plane or ProductFlow source records and the verifier checks the fields required for the selected compare scope.

## Record-Family Classification Vocabulary

CPWS-REQ-020: The accepted requirements MUST classify each record family as one of:

1. `required_authority`
2. `authority_preserving_projection`
3. `optional_supporting_evidence`
4. `projection_only`
5. `forbidden_substitute`
6. `out_of_scope`

CPWS-REQ-021: `required_authority` means verifier success depends on evidence from that family.

CPWS-REQ-022: `authority_preserving_projection` means the witness bundle may carry a bounded projection of a source authority record when the source record identity, digest-equivalent marker, or source path is preserved and the verifier checks the required fields.

CPWS-REQ-023: `optional_supporting_evidence` means the evidence may improve human review or later automation but cannot be required for first-slice verifier success.

CPWS-REQ-024: `projection_only` means the evidence may summarize authority but cannot replace required authority.

CPWS-REQ-025: `forbidden_substitute` means verifier success MUST fail closed if that evidence is used in place of required authority.

CPWS-REQ-026: `out_of_scope` means the evidence family is not part of the first trusted-run substrate claim.

## Accepted Record-Family Matrix

The first slice record-family matrix is:

| Record family | Classification | First-slice source evidence | Verifier question | Fail-closed condition |
|---|---|---|---|---|
| governed input | `required_authority` | `authority_lineage.governed_input`, `productflow_slice`, approval payload digest | What ProductFlow request was admitted and for which issue and seat? | Missing, drifted, or wrong epic/issue/seat fails as `governed_input_missing`. |
| workload/catalog classification | `optional_supporting_evidence` | governed start-path matrix and ProductFlow workload context | Which governed start path admitted the work? | Not required for current verifier success; if later required, missing catalog source becomes `workload_authority_missing`. |
| resolved policy snapshot | `required_authority` | `policy_snapshot_ref`, `policy_digest`, checkpoint policy digest | Which policy admitted the run and checkpoint? | Missing bundle or checkpoint policy identity fails as `policy_or_configuration_missing`. |
| resolved configuration snapshot | `required_authority` | `configuration_snapshot_ref`, run configuration snapshot id | Which configuration admitted the run? | Missing configuration identity fails as `policy_or_configuration_missing`. |
| run | `required_authority` | `authority_lineage.run` | Which governed run is canonical? | Missing or mismatched `run_id` fails as `canonical_run_id_drift`. |
| attempt | `authority_preserving_projection` | `authority_lineage.run.current_attempt_id` and attempt state | Which attempt was current for the effect? | Missing current attempt identity fails as `step_lineage_missing_or_drifted`. |
| step | `required_authority` | `authority_lineage.step` plus effect-journal step linkage | Which step explains the effect-journal entry? | Missing or contradictory step/effect linkage fails as `step_lineage_missing_or_drifted`. |
| approval request | `required_authority` | approval row fields copied into `authority_lineage.approval_request` | Was an approval-required tool seam requested for this run? | Missing or wrong approval target fails as `approval_request_missing_or_drifted`. |
| operator action | `required_authority` | approval resolution/operator action fields | Did an operator approve the continuation? | Missing or non-approved operator action fails as `missing_approval_resolution`. |
| checkpoint acceptance | `required_authority` | `authority_lineage.checkpoint` | Was continuation allowed from an accepted boundary? | Missing, wrong run, or non-accepted checkpoint fails as `checkpoint_missing_or_drifted`. |
| reservation | `required_authority` | `authority_lineage.reservation` and checkpoint reservation refs | What authority reserved or held the namespace before effect? | Missing source reservation evidence fails as `lease_source_reservation_not_verified` or `resource_or_lease_evidence_missing`. |
| lease | `authority_preserving_projection` | checkpoint lease refs and resource provenance ref | Which authority owned the namespace at execution? | Missing lease refs fail as `resource_or_lease_evidence_missing`; lease/source mismatch fails as `lease_source_reservation_not_verified`. |
| resource | `required_authority` | `authority_lineage.resource` | Does latest namespace resource authority agree with lease authority? | Missing or contradictory resource authority fails as `resource_or_lease_evidence_missing` or `resource_lease_consistency_not_verified`. |
| effect journal | `required_authority` | `authority_lineage.effect_journal` | What effect was authorized and observed? | Missing effect evidence fails as `missing_effect_evidence`; missing prior chain fails as `effect_prior_chain_not_verified`. |
| final truth | `required_authority` | `authority_lineage.final_truth` and run final truth id | What terminal result was assigned? | Missing final truth fails as `missing_final_truth`; mismatched terminal truth fails as `final_truth_cardinality_not_verified`. |
| bounded output artifact | `required_authority` | `artifact_refs`, `observed_effect` | Does bounded filesystem evidence match the claim? | Missing path or digest fails as `artifact_ref_missing` or `missing_output_artifact`; wrong content fails as `wrong_output_content`. |
| issue state read model | `authority_preserving_projection` | `observed_effect.issue_status` read from ProductFlow issue state | Did the target issue reach the bounded terminal state? | Wrong terminal state fails as `wrong_terminal_issue_status`; issue state alone cannot replace final truth. |
| contract verdict | `required_authority` | `contract_verdict` plus recomputation | Did the deterministic verdict pass on the bundle? | Missing or drifted verdict fails as `contract_verdict_missing` or `contract_verdict_drift`. |
| invariant model | `required_authority` | verifier-computed `trusted_run_invariant_model.v1` | Do accepted invariants pass on the same bundle evidence? | Missing or failing model blocks verifier success. |
| verifier report | `required_authority` for campaign only | `trusted_run_witness_report.v1` | Did bundle verification succeed without mutating workflow state? | Failed report blocks campaign success; missing side-effect-free proof blocks campaign promotion. |
| campaign report | `optional_supporting_evidence` for bundle verification, `required_authority` for `verdict_deterministic` | `build_campaign_verification_report` output | Are at least two successful reports stable? | One report or unstable signatures keep claim at `non_deterministic_lab_only`. |
| run summary | `projection_only` | `runs/<session_id>/run_summary.json` | Where are supporting run artifacts and resolver witnesses? | May support lookup and digest evidence; cannot replace run, checkpoint, effect, or final truth authority. |
| review package | `projection_only` | ProductFlow operator review package | What should a human inspect? | Cannot replace required authority. Missing source refs make it a forbidden substitute. |
| evidence graph | `projection_only` | run evidence graph artifacts | How is evidence visualized? | Cannot replace required authority. Graph-only success must fail closed. |
| Packet 1/2 blocks | `projection_only` | packet projections | What is the operator-facing summary? | Cannot replace authority records or verifier report. |
| model text semantics | `out_of_scope` | model response content | Was generated text semantically good? | Out of scope for this substrate claim. |

## Projection Discipline

CPWS-REQ-040: A projection MAY summarize authority records only when it carries source record refs, source paths, source record ids, or a digest-equivalent source marker.

CPWS-REQ-041: A projection MUST identify itself as projection-only when it is not the source authority.

CPWS-REQ-042: A projection MUST preserve missing-evidence markers instead of smoothing them into success-shaped summaries.

CPWS-REQ-043: A verifier MUST NOT accept a projection as a substitute for a required authority record unless the accepted matrix classifies that projection as `authority_preserving_projection`.

CPWS-REQ-044: A human-facing summary MUST name its claim tier or say that it is not claim authority.

CPWS-REQ-045: A projection that drops source refs, drops missing-evidence markers, or presents itself as native authority MUST be treated as a `forbidden_substitute`.

## Forbidden Substitute Rules

CPWS-REQ-050: `session_id` MUST NOT substitute for canonical governed `run_id`.

CPWS-REQ-051: artifact root paths MUST NOT substitute for canonical governed `run_id`.

CPWS-REQ-052: run summary status MUST NOT substitute for final truth.

CPWS-REQ-053: issue status MUST NOT substitute for final truth.

CPWS-REQ-054: approval status MUST NOT substitute for operator action evidence.

CPWS-REQ-055: checkpoint existence MUST NOT substitute for accepted checkpoint evidence.

CPWS-REQ-056: reservation refs MUST NOT substitute for lease/resource consistency.

CPWS-REQ-057: output file content MUST NOT substitute for effect-journal evidence.

CPWS-REQ-058: a review package MUST NOT substitute for a witness bundle.

CPWS-REQ-059: a campaign report MUST NOT substitute for individual successful verifier reports.

CPWS-REQ-060: a graph or Packet projection MUST NOT substitute for source authority.

## Failure Semantics

CPWS-REQ-070: Missing required authority MUST fail closed.

CPWS-REQ-071: Contradictory required authority MUST fail closed.

CPWS-REQ-072: Stale authority MUST fail closed when the bundle records enough evidence to detect staleness.

CPWS-REQ-073: Projection-only substitution MUST fail closed even if the projection contains success-shaped fields.

CPWS-REQ-074: Missing source refs on a projection used for proof MUST fail closed.

CPWS-REQ-075: If the current verifier cannot detect a substrate violation mechanically, it MUST emit a missing-substrate blocker instead of success.

The accepted failure vocabulary for new substrate blockers is:

| Blocker | Meaning |
|---|---|
| `workload_authority_missing` | A later slice requires catalog workload authority but the bundle does not provide it. |
| `authority_source_ref_missing` | A projection is used as evidence without a source ref, source path, source id, or digest-equivalent marker. |
| `projection_substitute_not_authority` | Projection-only evidence is used where source authority is required. |
| `stale_authority_not_excluded` | The bundle lacks enough freshness or latest-authority evidence for a requirement that depends on latest state. |
| `substrate_record_family_unclassified` | The bundle or verifier uses a record family not classified by the accepted matrix. |

Existing Trusted Run Witness and Trusted Run Invariant failure names SHOULD be reused when they precisely describe the failure.

## ProductFlow Current Coverage

The current ProductFlow Trusted Run Witness bundle already covers these substrate requirements:

| Requirement area | Current evidence | Coverage |
|---|---|---|
| governed input | `authority_lineage.governed_input`, `productflow_slice`, approval payload digest | covered |
| run authority | `authority_lineage.run.run_id` plus top-level `run_id` | covered |
| run-id resolver witness | `resolution_basis` and unique approval lookup | covered |
| policy/config evidence | policy/config refs plus checkpoint policy digest | covered |
| approval request/action | approval request fields and operator action fields | covered |
| checkpoint acceptance | accepted checkpoint fields | covered |
| step/effect linkage | step projection and effect journal linkage | covered for first slice |
| resource/lease consistency | resource id, checkpoint lease refs, resource provenance ref | covered for first slice |
| effect prior chain | latest prior journal id and prior digest | covered |
| final truth | final truth record plus run final truth id | covered |
| output artifact | artifact refs and observed effect fields | covered |
| invariant model | verifier-computed model output | covered |
| campaign stability | stable verdict and invariant signatures | covered |

Current evidence that remains intentionally bounded:

1. workload/catalog classification is not required for current verifier success
2. attempt identity is carried through run projection rather than a full independent attempt record
3. lease authority is checked through lease refs and resource provenance rather than a full serialized lease record
4. run summary remains resolver and artifact support evidence, not source authority
5. review package and graph evidence remain projection-only

## Implementation Handoff Requirements

CPWS-REQ-080: If the user accepts these requirements, durable substrate authority SHOULD be extracted as `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`.

CPWS-REQ-081: The extracted spec MUST reference `docs/specs/TRUSTED_RUN_WITNESS_V1.md` and `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md` instead of duplicating their schemas or invariant catalog.

CPWS-REQ-082: The first implementation SHOULD add a machine-readable substrate matrix to verifier output only if doing so strengthens fail-closed behavior or human auditability without duplicating the invariant model.

CPWS-REQ-083: The first implementation SHOULD add tests that prove projection-only evidence cannot replace required authority.

CPWS-REQ-084: If implementation changes trusted-run bundle fields, verifier report fields, canonical paths, or claim surfaces, it MUST update durable specs and `CURRENT_AUTHORITY.md` in the same change.

CPWS-REQ-085: If implementation only extracts the accepted requirements into a durable spec without behavior changes, `CURRENT_AUTHORITY.md` needs an update only when that spec becomes a canonical source of truth.

## Claim-Tier Requirements

CPWS-REQ-090: The requirements MUST preserve `non_deterministic_lab_only` for a single accepted bundle.

CPWS-REQ-091: The requirements MUST preserve `verdict_deterministic` as the maximum current ProductFlow trusted-run campaign claim tier.

CPWS-REQ-092: The requirements MUST NOT permit `replay_deterministic` or `text_deterministic` claims without the evidence required by `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

CPWS-REQ-093: Any human-facing statement derived from this lane MUST name the compare scope and claim tier.

## Acceptance Proof Requirements

Before this requirements lane can close as accepted, it MUST provide:

1. an accepted record-family matrix
2. an accepted verifier-question mapping
3. an accepted projection discipline rule set
4. fail-closed semantics for missing or contradictory substrate evidence
5. explicit missing-substrate blockers
6. a durable spec extraction decision
7. remaining implementation decisions

This draft provided all seven items and was accepted by the user's explicit continuation request on 2026-04-18.

## Resolved Decisions

1. The accepted output should become a standalone durable spec: `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`.
2. The durable spec should be a substrate and projection-discipline contract, not another copy of Trusted Run Witness or Trusted Run Invariants.
3. Current ProductFlow verifier success should not require workload/catalog evidence.
4. Current ProductFlow verifier success may use attempt and lease evidence as authority-preserving projections for the first slice.
5. Run summaries, review packages, evidence graphs, and Packet blocks remain projection-only unless a later spec explicitly promotes a bounded field as authority-preserving witness evidence.
6. First implementation should focus on projection-substitution fail-closed tests and durable spec extraction before any control-plane expansion.

## Remaining Implementation Decisions

1. exact shape of `CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
2. whether `trusted_run_invariant_model.v1` should expose a compact `substrate_matrix` block or keep substrate checks implicit through invariant checks
3. whether the witness bundle should add explicit `source_record_refs` metadata for every authority-lineage family
4. whether full lease records should become required in the next trusted-run slice
5. whether full attempt records should become required in the next trusted-run slice
6. how to test stale-authority detection without creating broad runtime convergence work
7. whether projection-only marker vocabulary should be shared across run summaries, graphs, packets, and review packages
