# Orket Proof-Carrying Governed Changes Implementation Plan

Last updated: 2026-04-19
Status: Active live lane
Owner: Orket Core

Accepted requirements: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_REQUIREMENTS_V1.md`
Primary authority dependencies:
1. `CURRENT_AUTHORITY.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
4. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
5. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
6. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
7. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
8. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
9. `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`
10. `docs/specs/TRUSTED_CHANGE_SCOPE_ADMISSION_STANDARD_V1.md`
11. `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`

Supporting lane docs:
1. `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_MECHANIZATION_TARGET_MAP_V1.md`
2. `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_SCOPE_CANDIDATE_MATRIX_V1.md`
3. `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_SCOPE_ADMISSION_AND_CATALOG_DRAFT_V1.md`

## Purpose

Turn governed proof from a future-lane requirements packet into an active implementation lane.

This lane governs:
1. proof-strengthening work on the current trusted-run foundation,
2. selection and delivery of the first externally publishable non-fixture trusted change scope,
3. scope-family productization needed to make additional trusted change scopes repeatable.

This lane does not, by itself:
1. broaden current public trust wording,
2. treat internal admitted compare scopes as externally admitted trust surfaces, or
3. authorize a new trusted change scope before scope-local evidence, wording, and proof all exist.

## Current Authority Context

As of 2026-04-18, this lane operates from the following authority-bounded position:

1. The current externally admitted public trust slice remains `trusted_repo_config_change_v1` with public wording bounded by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.
2. The internal admitted compare-scope set is broader than the current public trust slice; Trusted Run Witness authority now admits `trusted_run_productflow_write_file_v1`, `trusted_repo_config_change_v1`, and `trusted_terraform_plan_decision_v1`.
3. The current trusted-run witness, invariant, substrate, and offline-verifier stack lives under `docs/specs/` and remains the canonical foundation for this lane.
4. The active requirements authority for this lane is `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_REQUIREMENTS_V1.md`.
5. Under the active trust/publication authorities, no additional externally publishable trusted change scope is yet admitted beyond the current public trust slice.

## Governing Decisions

The following decisions govern this lane unless the roadmap or accepted requirements change:

1. The external/public trust slice remains narrower than the full internal admitted compare-scope set.
2. Public trust wording stays scope-local and evidence-bounded; promotion of new wording requires a separate same-change trust-boundary update when evidence supports it.
3. Durable authority for any admitted trusted change scope must resolve to `docs/specs/`, with `CURRENT_AUTHORITY.md` updated in the same change when canonical commands, paths, or contract surfaces change.
4. For this lane, the current priority invariant and substrate checks are fixed to the six requirement targets named in `PCGC-MTH-020`:
   - `step_lineage_missing_or_drifted` and step-lineage independence
   - `lease_source_reservation_not_verified`
   - `resource_lease_consistency_not_verified`
   - `effect_prior_chain_not_verified`
   - `final_truth_cardinality_not_verified`
   - `verifier_side_effect_absence_not_mechanically_proven`
5. Scope admission must reuse the current trusted-run evidence vocabulary rather than relabeling evidence from another compare scope.
6. Externally useful scope selection must prefer the smallest bounded task that an outside evaluator already recognizes as real work.

## Workstream Order

## Workstream 0 - Promote Governed Proof To A Live Lane

### Goal

Make governed proof a live project lane in this repo with one canonical implementation plan.

### Tasks

1. move the accepted requirements out of `docs/projects/future/governed-proof/` into `docs/projects/governed-proof/`
2. create this implementation plan as the canonical execution authority
3. put the lane on `docs/ROADMAP.md` under `Priority Now`
4. add the live project folder to the roadmap project index
5. run `python scripts/governance/check_docs_project_hygiene.py`

### Exit criteria

1. `docs/projects/governed-proof/` exists as the canonical non-archive project path
2. `docs/ROADMAP.md` points `Priority Now` at this plan, not at the requirements doc
3. no active governed-proof lane document remains parked under `docs/projects/future/`

### Current checkpoint

Workstream 0 is complete only while all of the following remain true in current repo authority:

1. `docs/projects/governed-proof/` is the canonical non-archive project path for this lane.
2. `docs/ROADMAP.md` points `Priority Now` at this plan.
3. no active governed-proof lane document remains under `docs/projects/future/`.

## Workstream 1 - Mechanization Foundation And Verifier Non-Interference

### Goal

Strengthen the current trusted-run proof foundation without broadening current public claims.

### Tasks

1. choose the bounded machine-checked or independently checkable model surface for the trusted-run invariant and substrate boundary
2. implement mechanization or independent evidence for the six fixed priority checks listed in `Governing Decisions` and mapped in `ORKET_PROOF_CARRYING_GOVERNED_CHANGES_MECHANIZATION_TARGET_MAP_V1.md`
3. add a mechanically constrained or independently checkable proof story for offline-verifier non-interference
4. make any still-uncovered limitation explicit in machine-readable proof output instead of treating it as closed
5. update `CURRENT_AUTHORITY.md` and any changed canonical proof docs in the same change if commands, paths, or support artifacts become authoritative

### Exit criteria

1. the six fixed priority checks have mechanized coverage or independently checkable evidence suitable for admission and publication decisions
2. offline-verifier non-interference is mechanically constrained or independently evidenced
3. remaining uncovered areas, if any, are explicit and truthful in proof outputs
4. no public trust wording is broadened unless accepted evidence supports it in the same change

### Current checkpoint

Completed on 2026-04-18 while all of the following remain true in current repo authority:

1. `python scripts/proof/verify_trusted_run_proof_foundation.py` remains the canonical Workstream 1 proof command.
2. `benchmarks/results/proof/trusted_run_proof_foundation.json` remains the canonical proof-foundation artifact for the six fixed priority checks.
3. `TRI-INV-031` and the ProductFlow plus First Useful Workflow witness verifier surfaces derive `side_effect_free_verification` from that proof artifact rather than from an asserted constant.
4. the proof-foundation artifact continues to expose positive and negative evidence for the exact six fixed targets named in `Governing Decisions`.

## Workstream 2 - First Externally Useful Scope Selection And Contract Extraction

### Goal

Select the first non-fixture trusted change scope and extract its durable authority.

### Tasks

1. evaluate candidate scopes against the external-usefulness requirements from the accepted lane requirements, using `ORKET_PROOF_CARRYING_GOVERNED_CHANGES_SCOPE_CANDIDATE_MATRIX_V1.md` as the lane-local comparison surface
2. choose one scope that is operationally legible and repeatable under a stable compare scope
3. extract the chosen scope's durable contract family into `docs/specs/` before implementation claims are made
4. define the scope's validator surface, allowed mutation boundary, required authority families, must-catch corruption set, canonical commands, output paths, and forbidden claims
5. prepare the scope's evaluator journey and bounded trust-wording delta for later promotion if evidence supports it

### Exit criteria

1. one first non-fixture scope is selected explicitly
2. the chosen scope's durable authority resolves to `docs/specs/`
3. the scope has a truthful evaluator path and scope-local publication boundary

### Current checkpoint

Completed on 2026-04-18 while all of the following remain true in current repo authority:

1. `trusted_terraform_plan_decision_v1` remains the explicitly chosen first non-fixture scope for Workstream 3.
2. the durable chosen-scope contract remains `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`.
3. the truthful inspection-only evaluator path remains `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`.
4. the chosen scope remains the same durable Terraform contract family carried forward into Workstream 3 and later publication gating.

## Workstream 3 - First External Scope Implementation And Proof

### Goal

Implement the chosen externally useful trusted change scope on top of the current trusted-run foundation.

### Tasks

1. add runtime support that reuses the existing witness, invariant, substrate, and offline-verifier model
2. implement the scope's deterministic validator or equivalent deterministic validation surface
3. add corruption coverage for the scope's must-catch set
4. add positive proof coverage for the scope's allowed claim tier ceiling
5. run the canonical live proof path and record observed path and observed result truthfully

### Exit criteria

1. the scope emits its live proof artifact, witness bundle, verifier report, offline claim report, and evaluator guide
2. the scope reaches only the claim ceiling that the offline verifier allows from actual evidence
3. the scope's public wording remains blocked until the separately governed publication boundary is updated truthfully

### Current checkpoint

Completed on 2026-04-18 while all of the following remain true in current repo authority:

1. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision.py` remains the canonical live proof command for this scope.
2. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py` remains the canonical campaign proof command for this scope.
3. `benchmarks/results/proof/trusted_terraform_plan_decision_live_run.json`, `benchmarks/results/proof/trusted_terraform_plan_decision_validator.json`, `benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json`, and `benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json` remain the canonical stable proof outputs for this scope.
4. `workspace/trusted_terraform_plan_decision/runs/<session_id>/trusted_run_witness_bundle.json` remains the canonical witness bundle root for this scope.
5. `trusted_terraform_plan_decision_v1` remains admitted internally only, not yet externally publishable, and not yet part of the current public trust slice.
6. the offline verifier continues to cap this scope at `verdict_deterministic` from current campaign evidence and continues to fail closed on replay or text determinism.

## Workstream 4 - Scope Family Productization

### Goal

Make trusted change scope admission repeatable across more than one effect class.

### Tasks

1. extract the stable scope-admission standard implied by the accepted requirements into durable authority as needed, using `ORKET_PROOF_CARRYING_GOVERNED_CHANGES_SCOPE_ADMISSION_AND_CATALOG_DRAFT_V1.md` as the lane-local drafting surface
2. publish the compare-scope catalog for admitted scopes with truthful claim ceilings and exposed proof limitations
3. standardize shared helper boundaries for validators, witness helpers, claim verification, and corruption testing
4. standardize a short scope card or equivalent summary surface for side-by-side scope comparison

### Exit criteria

1. admitted scopes can be compared through one truthful catalog
2. reusable helper boundaries exist for repeated scope delivery
3. the family story does not collapse different effect classes into one vague trust claim

### Current checkpoint

Completed on 2026-04-18 while all of the following remain true in current repo authority:

1. `docs/specs/TRUSTED_CHANGE_SCOPE_ADMISSION_STANDARD_V1.md` remains the durable admission standard for governed-proof compare scopes.
2. `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md` remains the truthful admitted compare-scope catalog and scope-card surface.
3. `scripts/proof/trusted_scope_family_support.py` remains the shared helper boundary for validator-backed campaign evaluation and offline claim verification across admitted non-ProductFlow compare scopes, with its split helpers kept under `scripts/proof/trusted_scope_family_*.py`.
4. the admitted-scope catalog continues to distinguish internal admitted scopes from the narrower externally publishable public trust slice and keeps scope-local claim ceilings and limitations explicit.

## Workstream 5 - Publication Boundary Update And Lane Closeout

### Goal

Close the lane only when the product-level trust story is supported by admitted evidence.

### Tasks

1. update `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` only if new evidence truthfully supports broader publication
2. sync `CURRENT_AUTHORITY.md`, `docs/ROADMAP.md`, and any new durable specs in the same change as authority changes
3. archive the lane only after the active roadmap entry can be removed truthfully

### Exit criteria

1. the lane exit criteria below are met
2. roadmap and authority docs no longer overstate or understate the shipped proof surface
3. the live lane can be archived without leaving active execution authority in `docs/projects/future/` or stale `Priority Now` entries

### Current checkpoint

Blocked on 2026-04-18 while all of the following remain true in current repo authority:

1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` still admits only `trusted_repo_config_change_v1` as the current externally publishable public trust slice.
2. `trusted_terraform_plan_decision_v1` remains internally admitted only under `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`.
3. the admitted Terraform campaign evidence still comes from the bounded local harness surfaced by `scripts/proof/run_trusted_terraform_plan_decision.py` and `scripts/proof/run_trusted_terraform_plan_decision_campaign.py`.
4. `python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json` now exists as the provider-backed governed proof path, but it is not yet admitted public evidence.
5. `python scripts/proof/prepare_trusted_terraform_live_setup_packet.py` remains the no-spend live setup packet generator, writes `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_packet.json`, and must execute zero provider calls.
6. `python scripts/proof/check_trusted_terraform_live_setup_preflight.py` remains the no-spend live setup preflight and must execute zero provider calls.
7. `python scripts/proof/check_trusted_terraform_publication_readiness.py` remains the fail-closed Workstream 5 gate and must report `publication_decision=ready_for_publication_boundary_update` before Terraform publication widening can be proposed.
8. `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py` remains the one-shot Workstream 5 gate sequence, fails fast by default when live provider inputs are absent, and must preserve blocked readiness until provider-backed governed-proof evidence succeeds.
9. `scripts/reviewrun/run_terraform_plan_review_live_smoke.py` remains the separate provider-backed runtime smoke seam for `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`.
10. the lane stays active on `docs/ROADMAP.md` until successful provider-backed governed-proof evidence supports a truthful public-boundary update or explicit retirement change lands.

## Strategic Completion Gate

This lane can close only when all of the following are true:

1. the six fixed priority invariant/substrate checks named in `Governing Decisions` have mechanized coverage or independently checkable evidence appropriate to admission and publication decisions
2. offline-verifier non-interference has a mechanically justified or independently checkable proof story
3. at least one externally useful non-fixture trusted change scope is durably specified, implemented, and live-proven
4. a truthful compare-scope catalog exists for admitted scopes
5. the adoption story remains centered on independently checkable bounded workflow success rather than generic orchestration features

## Planned Outputs

This lane is expected to produce:

1. a live governed-proof project lane under `docs/projects/governed-proof/`
2. durable scope and publication authority updates under `docs/specs/` as workstreams complete
3. mechanization or independent evidence for the six fixed trusted-run proof obligations
4. one first externally useful trusted change scope with a full proof and evaluator path
5. a truthful compare-scope catalog for admitted scopes
