# Orket NorthStar Second Governed Change Packet Family Requirements v1

Last updated: 2026-04-20
Status: Accepted requirements - active implementation lane
Owner: Orket Core

Implementation plan: `docs/projects/northstar-governed-change-packets/ORKET_NORTHSTAR_SECOND_GOVERNED_CHANGE_PACKET_FAMILY_IMPLEMENTATION_PLAN.md`

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

Guide and implementation dependencies:

1. `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`
2. `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`

Archive and history references:

1. `docs/projects/archive/northstar-governed-change-packets/NGCP04192026-LANE-CLOSEOUT/CLOSEOUT.md`
2. `docs/projects/archive/northstar-governed-change-packets/NGCP04192026-LANE-CLOSEOUT/ORKET_NORTHSTAR_GOVERNED_CHANGE_PACKETS_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/northstar-governed-change-packets/NGCP04192026-LANE-CLOSEOUT/ORKET_NORTHSTAR_GOVERNED_CHANGE_PACKETS_REQUIREMENTS_V1.md`

## Purpose And Delta Boundary

Define the next NorthStar increment after the first governed change packet family closeout.

This document is a delta contract for choosing and evaluating one next packet family candidate for possible public admission. It does not create a new proof vocabulary, a second scope-local contract, or a second public-trust authority surface.

This requirements increment exists to answer one bounded question:

```text
Can one already-defined next governed change family truthfully become the
second externally admitted public trust slice now, without broadening claims
beyond the evidence the current verifier and publication gates actually support?
```

This document does not:

1. redefine `trusted_terraform_plan_decision_v1`,
2. replace `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` as the public-trust boundary,
3. replace `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md` as the scope-local contract,
4. admit a second packet family by assertion alone, or
5. broaden product-level trust wording without same-change proof.

## NorthStar Statement

The product north star remains:

```text
Make governed changes independently verifiable before making them broader.
```

For this increment, "broader" means:

1. moving from one externally admitted public trust slice to two only if the second slice is supported by the current verifier and publication-gate evidence, and
2. refusing that expansion when the evidence remains blocked, degraded, or still internally admitted only.

## Intended Operator Outcome

The intended outside-operator outcome for this increment is:

```text
Given the current Terraform plan decision scope and its public-admission
gate surfaces, a skeptical outside operator can tell whether that scope is
publicly admitted, still internally admitted only, or blocked from admission,
and can identify the exact evidence boundary without trusting Orket narration
first.
```

This outcome is narrower than "Terraform is publicly admitted now." A truthful blocked result still satisfies this requirements increment if the blocker is explicit and independently inspectable.

## Terms

For this document:

1. **second governed change packet family** means the next compare-scope family being evaluated for possible public admission after `trusted_repo_config_change_v1`; it does not imply that admission has already occurred.
2. **selected family** means the single candidate fixed by this requirements doc for this increment.
3. **public admission** means addition of the selected family to the externally publishable public trust slice governed by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.
4. **blocked truth** means a truthful outcome where the selected family remains internally admitted only because a required proof, readiness gate, or publication gate is still failing or environment-blocked.
5. **support-only narrative** means guides, closeouts, and summaries that help evaluators navigate the proof but do not replace the authoritative evidence artifacts.

## Authority By Reference

NS2-GCP-REF-001: The canonical public-trust and publication boundary remains `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

NS2-GCP-REF-002: The canonical selected-family scope contract remains `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`.

NS2-GCP-REF-003: The canonical admitted-scope comparison surface remains `docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md`.

NS2-GCP-REF-004: This requirements doc MUST NOT be interpreted as a second canonical source for scope-local mutation boundaries, validator rules, forbidden claims, or public wording already governed elsewhere.

NS2-GCP-REF-005: Any public-admission update produced by this lane MUST resolve back to the durable authority docs above in the same change.

## Current Baseline To Preserve

The current truthful repo baseline is:

1. `trusted_repo_config_change_v1` remains the only externally admitted public trust slice.
2. `trusted_terraform_plan_decision_v1` remains internally admitted only.
3. `trusted_run_productflow_write_file_v1` remains internally admitted only.
4. the strongest currently truthful public claim ceiling remains `verdict_deterministic`.
5. replay determinism is not proven for the current public slice or for Terraform plan decision.
6. text determinism is not proven for the current public slice or for Terraform plan decision.
7. the current public trust story remains bounded to the current repo-config slice until the Terraform publication gates pass truthfully.
8. setup packets, no-spend preflights, dashboards, summaries, and narration remain support or gating surfaces rather than substitute proof authority.

## Candidate Evaluation And Selection Decision

This increment evaluates the currently relevant next-family options as follows.

| Candidate | Why it matters | Current strengths | Current blocker or weakness | Result |
|---|---|---|---|---|
| `trusted_terraform_plan_decision_v1` | real outside-operator decision work over bounded IaC review | durable scope contract, deterministic validator surface, evaluator guide, live local-harness proof, runtime-backed governed-proof path, publication-readiness gate, publication-gate sequence | still not publicly admitted because admitted successful provider-backed governed-proof evidence is not yet present | selected |
| `trusted_run_productflow_write_file_v1` | legitimate internal admitted governed-proof slice | already admitted internally and evidence-bearing | more internal-product context, weaker public evaluator legibility, weaker case for first second-family public admission | not selected |
| `trusted_repo_config_change_v1` | current public slice | already publicly admitted and packetized | already occupies the first external slot and therefore cannot satisfy the "next family" decision | not a candidate |

### Why Terraform Plan Decision Is Selected

The governing reasons for selecting `trusted_terraform_plan_decision_v1` are:

1. it is already scope-defined under durable authority rather than still being a proposal,
2. it is already validator-backed and internally admitted,
3. it represents recognized outside-operator work rather than a repo-only fixture,
4. its current blocker is a truthfully testable publication-readiness condition rather than a missing contract boundary, and
5. it is the smallest current next-family candidate with a credible path to broader evaluator usefulness without claiming whole-runtime trust.

### Why ProductFlow Write File Is Not Selected

ProductFlow write file is not selected for this increment because:

1. it remains more dependent on internal product context,
2. it does not currently provide a clearer public evaluator path than Terraform plan decision, and
3. selecting it instead would not reduce the current public-admission ambiguity as effectively as the Terraform path.

## Bounded Scope

This requirements increment is limited to:

1. choosing exactly one next packet family candidate,
2. evaluating that candidate against the existing public-admission gates,
3. updating operator or trust-facing material only if the evidence supports the wording in the same change,
4. truthfully pausing or closing the lane if the candidate remains blocked, and
5. keeping the current public trust slice unchanged unless the selected family clears the required same-change proof and gate surfaces.

This increment must not:

1. admit more than one additional packet family,
2. redefine the selected family's durable scope contract in a second location,
3. broaden public trust wording ahead of the readiness and publication gates,
4. claim replay determinism or text determinism,
5. treat setup packets, preflights, logs, dashboards, summaries, or narration as substitute proof authority,
6. publish the staged adversarial benchmark without explicit approval, or
7. relabel internal admission as public admission.

## Required Outputs

A complete truthful implementation of this requirements increment must produce all of the following:

1. one fixed selected family for the lane,
2. one truthful admission decision for that family: admitted now or blocked now,
3. one preserved mapping from that decision back to existing durable authority,
4. one same-change public-trust update if admission succeeds, or one same-change blocked or paused record if it does not, and
5. no duplicate scope-local contract surface under `docs/projects/northstar-governed-change-packets/`.

## Requirements

### Baseline Preservation

NS2-GCP-BL-001: `trusted_repo_config_change_v1` MUST remain the only externally admitted public trust slice until same-change evidence and authority updates admit the selected second family.

NS2-GCP-BL-002: The current truthful public claim ceiling MUST remain `verdict_deterministic` unless a different ceiling is separately supported and explicitly promoted through durable authority.

NS2-GCP-BL-003: This increment MUST preserve the distinction between:

1. internally admitted scopes,
2. externally admitted public trust slices,
3. proof-support surfaces, and
4. public wording authority.

NS2-GCP-BL-004: This increment MUST preserve the current truthful statement that replay determinism and text determinism are not yet proven for the selected family.

### Selected Family And Scope Discipline

NS2-GCP-SCP-001: This increment MUST evaluate only `trusted_terraform_plan_decision_v1` as the next packet family candidate.

NS2-GCP-SCP-002: The selected family's compare scope, mutation boundary, validator surface, claim ceiling, and forbidden claims MUST continue to resolve to `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md` rather than being redefined in a parallel NorthStar contract.

NS2-GCP-SCP-003: The selected family's evaluator path MUST continue to resolve to `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md` unless a same-change update truthfully improves that guide.

NS2-GCP-SCP-004: The selected family MUST continue to reuse the Terraform reviewer runtime boundary rather than relabeling unrelated evidence as Terraform governed-proof authority.

NS2-GCP-SCP-005: ProductFlow write file MAY remain a future candidate for a later lane, but it MUST NOT be implicitly reopened or silently substituted for Terraform plan decision in this increment.

### Evidence And Gate Discipline

NS2-GCP-EVD-001: Public admission for the selected family MUST require successful provider-backed governed-proof evidence plus passing results from the existing Terraform publication-readiness gate and publication-gate sequence.

NS2-GCP-EVD-002: The already-admitted local-harness evidence for the selected family MUST remain passing and MUST remain explicitly distinguished from provider-backed public-admission evidence.

NS2-GCP-EVD-003: The selected family's authoritative evidence package for public-admission evaluation MUST continue to include, at minimum:

1. the local-harness live proof,
2. the campaign report,
3. the offline claim-verifier report,
4. the runtime-backed governed-proof output,
5. the publication-readiness report, and
6. the publication-gate sequence report.

NS2-GCP-EVD-004: The no-spend setup packet and no-spend live setup preflight MUST remain preparation or inspection surfaces only. They MUST NOT be treated as proof of public admission by themselves.

NS2-GCP-EVD-005: If the provider-backed governed-proof runtime path remains blocked, degraded, or environment-blocked, the lane MUST record that outcome truthfully and MUST NOT bypass it by appealing to local-harness evidence alone.

NS2-GCP-EVD-006: Missing provider inputs, missing AWS quota, or other live-environment blockers MUST be reported as blockers or environment blockers rather than as silent omissions.

NS2-GCP-EVD-007: The selected family MUST NOT be called publicly admitted unless both:

1. `python scripts/proof/check_trusted_terraform_publication_readiness.py`, and
2. `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py`

report `publication_decision=ready_for_publication_boundary_update`.

### Claim And Publication Discipline

NS2-GCP-TR-001: Any public-admission update for the selected family MUST stay capped at the strongest claim tier the existing verifier evidence allows, and MUST NOT exceed `verdict_deterministic` without new accepted authority.

NS2-GCP-TR-002: This increment MUST continue to forbid replay-deterministic and text-deterministic claims for the selected family unless new proof and same-change authority updates land.

NS2-GCP-TR-003: This increment MUST continue to forbid claims that Terraform public admission proves:

1. Terraform apply safety,
2. infrastructure correctness in general,
3. arbitrary IaC workflow trust, or
4. whole-runtime mathematical soundness.

NS2-GCP-TR-004: If the selected family remains blocked, public trust wording MUST stay unchanged rather than widening through narrative caveats.

NS2-GCP-TR-005: If the selected family is admitted publicly, the same change MUST update:

1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, and
2. any affected current-authority references.

NS2-GCP-TR-006: Support-only narrative MUST remain explicitly subordinate to authority-bearing artifacts.

### Operator And Evaluator Discipline

NS2-GCP-OPS-001: Operator-facing material for this increment MUST let a skeptical evaluator tell whether Terraform plan decision is:

1. publicly admitted,
2. still internally admitted only, or
3. blocked from public admission.

NS2-GCP-OPS-002: Operator-facing material MUST continue to distinguish authority-bearing artifacts from support-only narrative.

NS2-GCP-OPS-003: Operator-facing material MUST identify the publication-readiness and publication-gate reports as the admission boundary for the selected family.

NS2-GCP-OPS-004: The evaluator path MUST remain explicit that a passing no-spend setup preflight is not publication evidence.

NS2-GCP-OPS-005: If the lane reaches blocked truth, the evaluator path MUST still make the blocker legible without repo archaeology.

### Lane Closeout Discipline

NS2-GCP-CLS-001: This increment MUST end in one of two truthful states only:

1. public admission shipped with same-change authority updates, or
2. blocked or paused with the blocker recorded explicitly.

NS2-GCP-CLS-002: The lane MUST NOT be closed as shipped if Terraform plan decision remains internally admitted only.

NS2-GCP-CLS-003: If the lane closes or pauses without public admission, the roadmap and lane docs MUST record that state truthfully and MUST NOT imply a hidden follow-on admission.

## Required Proof Envelope

The minimum proof envelope for admission evaluation is:

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

1. the local-harness live and campaign path remains passing and claim-capped at `verdict_deterministic`,
2. the positive public-admission path requires the runtime-backed governed-proof run to succeed and both publication gate outputs to report `publication_decision=ready_for_publication_boundary_update`, and
3. the blocked path is still acceptable only when the publication blockers are recorded truthfully and no public admission update follows.

## Acceptance Criteria

These requirements are accepted for implementation planning with the following fixed outcomes:

1. one next packet family is defined and evaluated,
2. the selected family is `trusted_terraform_plan_decision_v1`,
3. the implementation lane is limited to admission evaluation, supporting operator or trust-surface updates if the evidence passes, and truthful pause or closeout if it does not,
4. no additional packet family is selected or admitted by these requirements alone,
5. ProductFlow write file remains unselected for this increment, and
6. blocked truth is an allowed outcome, but silent or narrative-only widening is not.

## Resolved Decisions

1. Use the already-defined `trusted_terraform_plan_decision_v1` scope as the sole selected next-family candidate.
2. Reuse existing governed-proof durable authority instead of creating a duplicate NorthStar scope contract.
3. Keep the public claim ceiling capped at `verdict_deterministic` unless stronger same-change proof and authority land.
4. Treat a truthful blocked outcome as better than a broadened but unsupported public-admission claim.

## Remaining Open Questions

1. Whether the current live environment can clear the provider-backed governed-proof path truthfully enough for same-change public admission.
2. Whether admission, if it becomes possible, requires only trust-boundary updates or also narrower evaluator-guide wording updates.
3. Whether the lane will close as publicly admitted or pause with an explicit live-environment blocker.

## Reopen Trigger

Reopen or revise these requirements only when one of the following is explicitly requested:

1. replace Terraform plan decision with a different next-family candidate,
2. broaden the claim target beyond `verdict_deterministic`,
3. combine this lane with benchmark publication or a broader public trust rewrite, or
4. retire the lane without public admission.
