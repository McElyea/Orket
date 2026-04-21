# Orket NorthStar Second Governed Change Packet Family Implementation Plan

Last updated: 2026-04-20
Status: Paused checkpoint
Owner: Orket Core

Accepted requirements: `docs/projects/northstar-governed-change-packets/ORKET_NORTHSTAR_SECOND_GOVERNED_CHANGE_PACKET_FAMILY_REQUIREMENTS_V1.md`

Primary durable authority dependencies:

1. `CURRENT_AUTHORITY.md`
2. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
3. `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`
4. `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`
5. `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`
6. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
7. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
8. `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`
9. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`
10. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`

Guide and lane dependencies:

1. `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`
2. `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`

Archive and history references:

1. `docs/projects/archive/northstar-governed-change-packets/NGCP04192026-LANE-CLOSEOUT/CLOSEOUT.md`
2. `docs/projects/archive/northstar-governed-change-packets/NGCP04192026-LANE-CLOSEOUT/ORKET_NORTHSTAR_GOVERNED_CHANGE_PACKETS_IMPLEMENTATION_PLAN.md`

## Purpose

Evaluate the already-internal `trusted_terraform_plan_decision_v1` scope as the next NorthStar governed change packet family for possible public admission.

This lane does not redefine the Terraform scope contract, replace the governed-proof lane's durable scope work, or broaden public trust claims ahead of admitted evidence. It decides whether Terraform plan decision can truthfully become the second externally admitted packet family now.

## Bounded Scope

This lane is limited to:

1. making the NorthStar second-family requirements the active roadmap lane
2. freezing the selected candidate to `trusted_terraform_plan_decision_v1`
3. evaluating that candidate against the existing Terraform publication gates
4. updating public-admission material only if those gates pass
5. pausing or closing the lane truthfully if the gates remain blocked

This lane must not:

1. choose a second candidate in parallel
2. admit a third packet family
3. weaken the existing Terraform publication gates
4. claim replay determinism or text determinism
5. relabel governed-proof support artifacts as public proof authority
6. publish the staged adversarial benchmark without explicit approval
7. relabel internal admission as public admission

## Current Authority Context

As of 2026-04-20, this lane starts from the following truthful position:

1. `trusted_repo_config_change_v1` remains the only externally admitted public trust slice.
2. `trusted_terraform_plan_decision_v1` already exists as an internally admitted compare scope under `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`.
3. `trusted_run_productflow_write_file_v1` remains internally admitted only and is not the selected candidate for this lane.
4. The Terraform scope already has a truthful evaluator guide, readiness gate, publication-gate sequence, provider-backed governed-proof runtime path, and local-harness governed-proof evidence surfaces.
5. The current blocker for Terraform public admission is not missing scope definition. It is missing admitted successful provider-backed governed-proof evidence.
6. Replay determinism is not proven for the current public slice or for Terraform plan decision.
7. Text determinism is not proven for the current public slice or for Terraform plan decision.
8. The current public trust story remains bounded to the repo-config slice until the Terraform publication gates pass truthfully.
9. Setup packets, no-spend preflights, dashboards, summaries, and narration remain support or gating surfaces rather than substitute proof authority.
10. The governed-proof lane remains paused, but its durable scope contract and existing readiness gates are dependencies for this lane rather than duplicate execution authority.

## Governing Decisions

The following decisions govern this lane unless the accepted requirements change:

1. `trusted_terraform_plan_decision_v1` is the sole selected next-family candidate.
2. The selected family's compare scope, mutation boundary, validator surface, claim ceiling, and forbidden claims remain governed by `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`.
3. The selected family must continue to reuse the Terraform reviewer runtime boundary from `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md` and must not relabel unrelated evidence as Terraform governed-proof authority.
4. The current public trust boundary remains governed by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.
5. The maximum currently targetable public claim ceiling for this lane remains `verdict_deterministic`.
6. Local-harness passing evidence remains required and must remain explicitly distinct from provider-backed admission evidence.
7. The no-spend setup packet and no-spend live setup preflight are preparation or inspection surfaces only and are not publication evidence by themselves.
8. Failure to clear the publication gates results in blocked or paused truth, not fallback public admission.
9. Support-only narrative remains subordinate to authority-bearing artifacts.

## Workstream 0 - Authority Handoff

### Goal

Make this plan the active roadmap authority for the second-family NorthStar increment.

### Tasks

1. create the active `docs/projects/northstar-governed-change-packets/` project folder
2. keep the requirements document as a companion, not the roadmap entry target
3. put this lane on `docs/ROADMAP.md` under `Priority Now`
4. add the project folder to the roadmap Project Index
5. run `python scripts/governance/check_docs_project_hygiene.py`

### Exit criteria

1. `docs/projects/northstar-governed-change-packets/` exists as the canonical non-archive project path for this lane
2. the roadmap `Priority Now` entry points to this implementation plan
3. the Project Index includes `northstar-governed-change-packets`

### Current checkpoint

Completed on 2026-04-20 while the lane was active. After the 2026-04-20 pause, this plan remains the canonical pause and reopen authority for the lane.

The following remain true:

1. this implementation plan remains the canonical roadmap authority for the paused lane
2. the requirements document remains a companion document under the same active project folder
3. the Project Index includes `northstar-governed-change-packets`

## Workstream 1 - Candidate Freeze And Authority Alignment

### Goal

Select exactly one next packet family without creating duplicate scope authority.

### Tasks

1. freeze the selected candidate to `trusted_terraform_plan_decision_v1`
2. keep the selected family's compare scope, mutation boundary, validator surface, claim ceiling, and forbidden claims anchored to `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`
3. keep the evaluator guide anchored to `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`
4. preserve reuse of the Terraform reviewer runtime boundary and prohibit relabeling unrelated evidence as Terraform governed-proof authority
5. record why ProductFlow is not selected for this increment
6. keep the current public trust slice unchanged until the readiness gates pass

### Exit criteria

1. exactly one next-family candidate is selected
2. the selected candidate's durable authority still resolves to `docs/specs/`
3. the selected family's compare scope, mutation boundary, validator surface, claim ceiling, and forbidden claims remain frozen to the durable scope contract
4. no parallel scope contract is created under the NorthStar lane docs
5. the selected family continues to reuse the Terraform reviewer runtime boundary truthfully

### Current checkpoint

Completed on 2026-04-20 while the following remain true:

1. `trusted_terraform_plan_decision_v1` remains the sole selected candidate
2. `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md` remains the durable scope contract for compare scope, mutation boundary, validator surface, claim ceiling, and forbidden claims
3. `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md` remains the evaluator guide
4. `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md` remains the reusable runtime boundary for this family
5. `trusted_run_productflow_write_file_v1` remains unselected for this lane

## Workstream 2 - Admission Readiness Proof

### Goal

Determine whether Terraform plan decision can truthfully join the externally publishable public trust slice now.

### Tasks

1. rerun the local-harness live proof for the selected family
2. rerun the selected family's campaign proof
3. rerun the offline claim verifier for the selected family's current claim ceiling
4. rerun or inspect the no-spend live setup preflight as needed
5. rerun the provider-backed governed-proof runtime path when the required live inputs exist
6. rerun the Terraform publication-readiness gate
7. rerun the Terraform publication-gate sequence
8. record the observed path and observed result truthfully as `success`, `failure`, or `environment blocker`
9. keep the local-harness evidence explicitly distinguished from provider-backed admission evidence
10. keep the no-spend setup packet and live setup preflight explicitly identified as preparation or inspection surfaces, not publication evidence
11. treat missing provider inputs, missing quota, or similar live-environment blockers as explicit blockers or environment blockers rather than bypassing them with local-harness evidence alone

### Exit criteria

1. the lane has a truthful yes-or-no answer on whether the selected family is ready for public admission now
2. positive admission requires gate outputs that report `publication_decision=ready_for_publication_boundary_update`
3. the full minimum admission-evaluation proof envelope from the requirements has been rerun or truthfully reported blocked
4. local-harness evidence remains passing and explicitly distinct from provider-backed admission evidence
5. blocked evidence remains explicit rather than silently waived
6. no-spend preflight remains explicit support or inspection evidence rather than public-admission proof

### Required proof

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision.py
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json
python scripts/proof/check_trusted_terraform_live_setup_preflight.py
python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json
python scripts/proof/check_trusted_terraform_publication_readiness.py
python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py
python scripts/governance/check_docs_project_hygiene.py
```

Expected observed result:

1. local-harness live proof, campaign proof, and offline claim verification remain passing and claim-capped at `verdict_deterministic`
2. a positive public-admission path requires the runtime-backed governed-proof output to succeed and both gate outputs to report `publication_decision=ready_for_publication_boundary_update`
3. the no-spend setup preflight may pass and still does not count as publication evidence by itself
4. a blocked path remains truthful only when readiness or gate outputs remain blocked or environment-blocked, the blocker is recorded explicitly, and no public admission follows

### Current checkpoint

Completed on 2026-04-20 with a blocked public-admission result while the following remain true:

1. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision.py` reported `observed_result=success`, `workflow_result=success`
2. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py` reported `observed_result=success`, `claim_tier=verdict_deterministic`
3. `python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json` reported `observed_result=success`, `claim_status=allowed`, `claim_tier=verdict_deterministic`
4. `python scripts/proof/check_trusted_terraform_live_setup_preflight.py` reported `observed_result=environment blocker`, `provider_calls_executed=0`, with missing required non-secret env inputs `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI`, `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID`, and `AWS_REGION`
5. `python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json` reported `observed_result=environment blocker`, `execution_status=environment_blocker`
6. `python scripts/proof/check_trusted_terraform_publication_readiness.py` reported `observed_result=environment blocker`, `publication_decision=blocked`
7. `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py` reported `observed_result=environment blocker`, `publication_decision=blocked`, `execution_mode=preflight_blocked`
8. the truthful current answer to Workstream 2 is "not ready for public admission now"

## Workstream 3 - Public Admission Surface

### Goal

Update public trust and operator material only if Workstream 2 proves the selected family is ready.

### Tasks

1. update `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` only if the selected family clears the required gates
2. update `CURRENT_AUTHORITY.md` in the same change if canonical public-admission references change
3. update the Terraform evaluator guide only if the evidence supports a narrower or broader truthful operator story
4. identify the publication-readiness report and publication-gate report as the operator-facing admission boundary for the selected family
5. keep the evaluator path explicit that a passing no-spend setup preflight is not publication evidence
6. keep supported and unsupported claims explicit and claim-capped, including explicit prohibition on implying Terraform apply safety, infrastructure correctness in general, arbitrary IaC workflow trust, or whole-runtime mathematical soundness
7. keep support-only narrative subordinate to authority-bearing artifacts
8. preserve a same-change mapping from any admission decision back to the durable authority docs

### Exit criteria

1. any public-admission wording names the compare scope and claim ceiling explicitly
2. no public wording outruns the actual verifier evidence
3. the evaluator-facing story identifies the publication-readiness and publication-gate reports as the admission boundary
4. the evaluator path remains explicit that a passing no-spend setup preflight is not publication evidence
5. support-only narrative remains subordinate to authority-bearing artifacts
6. blocked truth, if it remains, is legible to evaluators without repo archaeology

### Required proof

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision.py
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json
python scripts/proof/check_trusted_terraform_publication_readiness.py
python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py
python scripts/governance/check_docs_project_hygiene.py
```

Expected observed result:

1. a positive path updates public-admission wording only when the gate outputs pass and the supporting local-harness and offline-claim evidence remains aligned
2. a blocked path keeps public trust wording unchanged, keeps blocked truth explicit, and still passes docs project hygiene

### Current checkpoint

Completed on 2026-04-20 on the blocked path while the following remain true:

1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` remains unchanged because the selected family did not clear the required publication gates
2. `CURRENT_AUTHORITY.md` remains unchanged because no canonical public-admission surface changed
3. the selected family remains internally admitted only
4. the operator-facing admission boundary remains the publication-readiness report plus the publication-gate report
5. the evaluator path continues to warn that a passing no-spend setup preflight is not publication evidence

## Workstream 4 - Lane Closeout Or Pause

### Goal

Close or pause the lane without leaving stale active roadmap authority.

### Tasks

1. close the lane as shipped if Terraform public admission lands truthfully
2. otherwise pause or archive the lane with explicit blocker truth
3. when admission does not land, record the blocked or paused state in one same-change authoritative lane artifact: this implementation plan while paused, or an archive closeout record if the lane is closed
4. update the roadmap in the same change so no obsolete active entry remains and no hidden follow-on admission is implied
5. run `python scripts/governance/check_docs_project_hygiene.py`

### Exit criteria

1. the lane ends in one of two truthful states only: public admission shipped with same-change authority updates, or blocked or paused with the blocker recorded explicitly
2. the roadmap no longer overstates active second-family work
3. remaining blockers or limits are recorded truthfully in an authoritative lane artifact
4. completed or archived lane docs do not remain in active `docs/projects/`
5. no closeout or pause wording implies a hidden follow-on admission

### Required proof

```text
python scripts/governance/check_docs_project_hygiene.py
```

Expected observed result: pass.

### Current checkpoint

Paused on 2026-04-20 after Workstream 2 and Workstream 3 exhausted the lane's local work while the following remain true:

1. the lane ends on the blocked truthful path rather than public admission
2. the authoritative blocked-state record for this pause is this implementation plan
3. the roadmap no longer carries this lane under `Priority Now`
4. the selected family remains blocked from public admission because provider-backed governed-proof evidence is still missing and the current live environment lacks required non-secret inputs `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI`, `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID`, and `AWS_REGION`
5. public trust wording remains unchanged and the externally admitted public trust slice remains only `trusted_repo_config_change_v1`

## Reopen Criteria

Reopen this lane only when one of the following is true:

1. a bounded change can truthfully provide the required non-secret live inputs `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI`, `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID`, and `AWS_REGION` or `AWS_DEFAULT_REGION`, rerun the full Workstream 2 proof envelope, and re-evaluate the publication-readiness and publication-gate outputs in the same change, or
2. the lane is explicitly reopened for retirement instead of public-admission completion.
