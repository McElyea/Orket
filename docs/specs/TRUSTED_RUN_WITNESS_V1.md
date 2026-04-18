# Trusted Run Witness v1

Last updated: 2026-04-18
Status: Active contract
Owner: Orket Core

This spec defines the bounded trusted-run witness contract for Orket.

The first slice is deliberately narrow. It does not claim full replay determinism, broad workflow correctness, or public publication readiness. It proves a deterministic verdict over one governed ProductFlow `write_file` run and records the evidence needed for an offline verifier to fail closed on missing or drifting authority.

The second admitted slice is the First Useful Workflow Slice in `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`. It uses the same witness bundle and report schemas with compare scope `trusted_repo_config_change_v1`, but it has its own contract verdict surface and validator surface. ProductFlow evidence MUST NOT be relabeled as the useful workflow slice.

## Claim Surface

First slice identity:

1. compare scope: `trusted_run_productflow_write_file_v1`
2. operator surface: `trusted_run_witness_report.v1`
3. contract verdict surface: `trusted_run_contract_verdict.v1`
4. witness bundle schema: `trusted_run.witness_bundle.v1`
5. invariant model surface: `trusted_run_invariant_model.v1`
6. substrate model surface: `control_plane_witness_substrate.v1`
7. canonical witness bundle root: `runs/<session_id>/trusted_run_witness_bundle.json`
8. canonical verifier proof output: `benchmarks/results/proof/trusted_run_witness_verification.json`
9. canonical offline claim verifier output: `benchmarks/results/proof/offline_trusted_run_verifier.json`
10. target claim tier: `verdict_deterministic`
11. single-run fallback claim tier: `non_deterministic_lab_only`

The first slice extends the canonical ProductFlow governed `write_file` path:

1. epic id: `productflow_governed_write_file`
2. issue id: `PF-WRITE-1`
3. canonical governed run id: ProductFlow turn-tool `run_id`
4. bounded output path: `agent_output/productflow/approved.txt`
5. normalized output content: `approved`
6. terminal issue status: `done`
7. required approval seam: `approval_required_tool:write_file`

Second slice identity:

1. compare scope: `trusted_repo_config_change_v1`
2. operator surface: `trusted_run_witness_report.v1`
3. contract verdict surface: `trusted_repo_change_contract_verdict.v1`
4. validator surface: `trusted_repo_config_validator.v1`
5. bounded output path: `repo/config/trusted-change.json`
6. canonical fixture workspace: `workspace/trusted_repo_change/`
7. durable contract: `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`

## Bundle Schema

A `trusted_run.witness_bundle.v1` bundle MUST contain:

1. `schema_version`
2. `bundle_id`
3. `run_id`
4. `session_id`
5. `compare_scope`
6. `operator_surface`
7. `claim_tier`
8. `policy_digest`
9. `policy_snapshot_ref`
10. `configuration_snapshot_ref`
11. `control_bundle_ref`
12. `control_bundle_digest`
13. `artifact_refs`
14. `authority_lineage`
15. `observed_effect`
16. `contract_verdict`

`session_id` and artifact-root paths are locators only. They MUST NOT substitute for the governed turn-tool `run_id`.

All file paths stored in the bundle MUST be workspace-relative or repo-relative unless a source contract explicitly requires a local absolute path. Each included artifact MUST be identified by path plus digest or by durable record id plus digest-equivalent integrity reference.

## Required Authority Matrix

The first witness bundle MUST include or reference these evidence families:

| Evidence family | Required source | Failure semantics |
|---|---|---|
| governed input | ProductFlow admitted epic, issue, seat, and approval payload evidence | missing or drifted input fails verification |
| policy snapshot | target run policy snapshot id plus checkpoint policy digest | missing policy identity fails verification |
| configuration snapshot | target run configuration snapshot id | missing configuration identity fails verification |
| run authority | governed turn-tool `RunRecord` projection | missing or mismatched `run_id` fails verification |
| attempt authority | target run current attempt projection | missing attempt identity fails verification |
| step authority | target step projection or effect-journal step linkage | missing step evidence fails verification |
| approval request | `approval_required_tool:write_file` request | missing request fails verification |
| operator action | approval resolution/operator action record | missing resolution fails verification |
| checkpoint authority | accepted same-attempt checkpoint | missing or drifted checkpoint fails verification |
| reservation and lease | namespace reservation or checkpoint acceptance reservation and lease refs | missing ownership evidence blocks success claims |
| effect journal | effect-journal entries for `write_file` and status mutation | missing or contradicted effect evidence blocks success claims |
| deterministic verdict | `trusted_run_contract_verdict.v1` | missing verdict fails verification |
| final truth | target-side `FinalTruthRecord` | missing final truth fails verification |

Review packages, run graphs, Packet 1/2 projections, replay reviews, and summaries MAY be included as supporting evidence. They MUST NOT replace required authority.

## Contract Verdict

`trusted_run_contract_verdict.v1` MUST mechanically check:

1. exact output path equals `agent_output/productflow/approved.txt`
2. normalized output content equals `approved`
3. terminal issue status equals `done`
4. approval request reason equals `approval_required_tool:write_file`
5. approval resolution is present and approved
6. accepted checkpoint evidence exists for the same governed run
7. resource, reservation, and lease evidence exists
8. effect-journal evidence exists with no residual uncertainty
9. final truth result is `success` with sufficient evidence
10. governed `run_id` aligns across required authority surfaces

The stable must-catch outcomes are:

1. `missing_output_artifact`
2. `wrong_output_content`
3. `missing_approval_resolution`
4. `missing_effect_evidence`
5. `missing_final_truth`
6. `canonical_run_id_drift`

The verdict signature MUST be stable across equivalent successful executions and MUST exclude timestamps and run-specific identifiers.

Verifier acceptance also requires the bundle to pass `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md` and `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`. The invariant model emits `trusted_run_invariant_model.v1` with an `invariant_signature_digest`; the substrate model emits `control_plane_witness_substrate.v1` with a `substrate_signature_digest`. Both digests must be stable across equivalent successful executions and exclude timestamps and run-specific identifiers.

## Claim Tiers

A single valid bundle remains `non_deterministic_lab_only`.

`verdict_deterministic` requires at least two equivalent ProductFlow trusted-run executions or a campaign report showing:

1. every included bundle verifies successfully
2. the verdict signature digest is stable
3. the invariant model signature digest is stable
4. the substrate model signature digest is stable
5. the must-catch outcome set is stable
6. the compare scope remains `trusted_run_productflow_write_file_v1`
7. the operator surface remains `trusted_run_witness_report.v1`

The first implementation MUST NOT claim `replay_deterministic` unless it adds replay evidence that satisfies `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

The first implementation MUST NOT claim `text_deterministic` unless byte identity or output-hash identity is explicitly in scope and proven on that same scope.

## Verification

Verification over a witness bundle MUST be side-effect free. The verifier MAY write its own report artifact, but bundle evaluation itself must be pure inspection.

The verifier report MUST include `trusted_run_invariant_model`, `invariant_model_signature_digest`, `control_plane_witness_substrate`, and `substrate_signature_digest`. Missing or failing invariant or substrate output is missing evidence and blocks verifier success.

Verification MUST fail closed when:

1. the canonical `run_id` drifts across required authority surfaces
2. final truth is missing
3. the contract verdict is missing
4. approval resolution evidence is missing
5. effect evidence is missing or contradicted
6. `claim_tier` or `compare_scope` is missing
7. normalized output content is not `approved`
8. `session_id` no longer agrees with the governed run resolver witness

The canonical verifier proof output is `benchmarks/results/proof/trusted_run_witness_verification.json` and MUST be written with the repository diff-ledger writer convention.

Offline claim assignment over witness bundle, single-report, and campaign-report evidence is governed by `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`. That verifier must not replace bundle verification and may only preserve or downgrade claims from existing evidence.
