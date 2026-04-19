# Orket Proof-Carrying Governed Changes Requirements v1

Last updated: 2026-04-18  
Status: Accepted requirements - active implementation lane  
Owner: Orket Core

Implementation plan: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`

Primary dependencies:
1. `CURRENT_AUTHORITY.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
4. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
5. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
6. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
7. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
8. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`

## Purpose And Delta Boundary

Define the next strategic requirements for Orket after the current bounded trusted-run proof slice.

In this document, "current bounded trusted-run proof slice" refers to the currently externally admitted public trust slice described by the active trust/publication authorities, not to the full set of admitted internal compare scopes or experimental proof surfaces.

This document is a delta contract. It does **not** redefine the canonical trust thesis, public trust wording, or publication boundary already governed by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

This document exists to define what must be added next so that the current trusted-run foundation can grow into a reusable family of externally meaningful trusted change scopes without weakening current truth discipline.

This document governs requirements for expanding from the currently externally admitted public trust slice to additional externally publishable trusted change scopes, subject to scope-local authority, evidence, and claim ceilings.

The required strategic direction is:

```text
Orket should extend the current trusted-run proof foundation into a
proof-carrying workflow runtime for governed changes.
```

In this document, that direction means:
1. expanding from the currently externally admitted public trust slice to a family of additional externally publishable trusted change scopes,
2. strengthening the machine-checkable foundation around the witness, invariant, substrate, and offline-verifier boundary,
3. defining what makes a new compare scope externally useful rather than merely demonstrative, and
4. defining what packaging and evaluator experience are required before a new scope can become a credible external adoption surface.

## Authority By Reference

PCGC-REF-001: The canonical trust thesis and external trust reason remain governed by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

PCGC-REF-002: The current public publication boundary, claim ceiling wording, and adoption-limitation wording remain governed by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

PCGC-REF-003: This document MUST NOT be interpreted as a second canonical source for public trust wording.

PCGC-REF-004: This document MAY define requirements for future trusted change scopes, but any public wording for those scopes must still be promoted separately through the governing trust-reason contract.

## Non-Goals

This document does not:
1. broaden current public trust claims beyond the currently admitted slice,
2. claim that Orket as a whole is mathematically proven,
3. replace the active witness, invariant, substrate, offline verifier, or trust-reason contracts,
4. define UI requirements,
5. define extension packaging requirements, or
6. define roadmap placement or phase-order authority.

## Terms

For this document:

1. **proof-carrying workflow runtime** means a runtime that can emit the evidence package and offline-verifiable claim boundary needed to justify a bounded success claim for an admitted compare scope;
2. **governed change** means an admitted workflow scope that performs a bounded effect under declared policy, emits authority evidence for that effect, and constrains the claim that may be made about that effect;
3. **trusted change scope** means a compare scope admitted under this strategy, with a scope-specific contract, validator surface if applicable, witness bundle, invariant model use, substrate model use, offline claim rules, and evaluator journey;
4. **claim discipline** means the requirement that Orket refuse stronger claims than the available evidence supports;
5. **externally useful** means meaningful outside the repo as a real operational task, not merely a synthetic proof fixture.

## Current Baseline To Preserve

PCGC-BL-001: The current externally admitted trust slice MUST remain `trusted_repo_config_change_v1` until a new compare scope is separately admitted by accepted contract.

PCGC-BL-002: Current truthful public wording MUST remain bounded by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

PCGC-BL-003: Nothing in this document may be used to imply that replay determinism or text determinism are already proven for the current useful workflow slice.

PCGC-BL-004: The currently admitted trusted-run machinery MUST remain the canonical foundation for future trusted change scopes unless and until a successor contract is accepted.

PCGC-BL-005: New strategic work MUST extend the current witness-bundle, invariant, substrate, and offline-verifier story rather than bypassing it with a parallel proof vocabulary.

## Strategic Objective

PCGC-OBJ-001: Orket MUST define and ship a family of trusted change scopes that reuse the current trusted-run evidence model while remaining truthful about each scope's exact claim ceiling.

PCGC-OBJ-002: At least one next trusted change scope MUST be externally meaningful and non-fixture-bounded.

PCGC-OBJ-003: Each trusted change scope MUST give an evaluator a concrete answer to all of the following:
1. what was requested,
2. what policy admitted or denied it,
3. what exact effect was attempted,
4. what deterministic validator checked it,
5. what final truth was published,
6. what witness bundle captures the evidence, and
7. what highest claim tier the offline verifier allows from that evidence.

## Trusted Change Scope Family Requirements

PCGC-SCP-001: Orket MUST define a stable admission process for new trusted change scopes.

PCGC-SCP-002: Every trusted change scope MUST define all of the following in one accepted contract family:
1. compare scope name,
2. operator surface,
3. contract verdict surface,
4. validator surface if the scope uses one,
5. bounded effect surface,
6. allowed mutation boundary,
7. required authority families,
8. must-catch corruption set,
9. single-run fallback claim tier,
10. highest currently allowed campaign claim tier,
11. canonical live proof command or commands,
12. canonical witness output path,
13. canonical offline verifier command, and
14. explicit non-goals and forbidden claims for that scope.

PCGC-SCP-003: A trusted change scope MUST NOT be admitted if it requires relabeling evidence from another compare scope.

PCGC-SCP-004: A trusted change scope MUST NOT be admitted if its success depends only on logs, summaries, review packages, or projections that existing trusted-run contracts already classify as non-authoritative.

PCGC-SCP-005: A trusted change scope SHOULD be small enough that its effect boundary, validator boundary, and failure semantics are legible to an outside evaluator in one short guide.

PCGC-SCP-006: Example externally meaningful bounded-work candidates include:
1. trusted repo patch change,
2. trusted Terraform plan decision,
3. trusted SQL migration apply,
4. trusted issue creation, or
5. trusted config rollout.

PCGC-SCP-007: A scope MUST NOT be admitted merely because it is easy to demo. It MUST satisfy the external-usefulness requirements from this document.

## Mathematical Foundation Requirements

### Abstract Model Boundary

PCGC-MTH-001: Orket MUST maintain a finite abstract model for every admitted trusted change scope.

PCGC-MTH-002: The abstract model MUST state the theorem boundary in bounded terms rather than implying whole-system proof.

PCGC-MTH-003: The canonical theorem shape for an admitted scope MUST remain structurally equivalent to:

```text
If the side-effect-free verifier accepts a witness bundle for an admitted
compare scope, then the serialized evidence satisfies the matching invariant
model, substrate model, and scope-specific claim rules for that compare scope.
```

PCGC-MTH-004: Scope-specific docs MUST distinguish between:
1. execution truth,
2. witness serialization truth,
3. invariant-model truth,
4. substrate consistency truth, and
5. claim-tier eligibility truth.

### Mechanized Model Strengthening

PCGC-MTH-010: Orket MUST add a machine-checked model for the trusted-run substrate and invariant boundary.

PCGC-MTH-011: The first mechanized model MAY be bounded and finite-state, but it MUST be able to express:
1. forbidden success states,
2. missing-evidence blockers,
3. authority cardinality constraints,
4. lineage constraints,
5. effect-chain constraints, and
6. claim downgrade behavior.

PCGC-MTH-012: The mechanized model MUST be authoritative for the subset of invariants it covers and MUST truthfully expose anything still outside that coverage.

PCGC-MTH-013: Mechanized coverage MUST start with the currently exposed trusted-run checks whose correctness most directly affects claim discipline, witness integrity, or verifier trust.

### Mechanization Coverage Boundary

PCGC-MTH-020: Initial mechanization or independent-evidence work SHOULD cover the currently exposed trusted-run checks associated with:
1. `step_lineage_missing_or_drifted` and step-lineage independence,
2. `lease_source_reservation_not_verified`,
3. `resource_lease_consistency_not_verified`,
4. `effect_prior_chain_not_verified`,
5. `final_truth_cardinality_not_verified`, and
6. `verifier_side_effect_absence_not_mechanically_proven`.

PCGC-MTH-021: This requirement is about mechanizing or independently evidencing those checks where they remain relevant to admission, promotion, or publication boundaries, not about reasserting that the current accepted bundle surface has failed to close its current bounded proof lane.

PCGC-MTH-022: If any admitted scope still carries an exposed limitation in one of those areas, that limitation MUST remain explicit in the scope's proof output and promotion boundary.

PCGC-MTH-023: No later publication wording may silently treat an unresolved limitation as covered.

### Verifier Non-Interference

PCGC-MTH-030: The offline verifier MUST be mechanically constrained or mechanically evidenced as side-effect free with respect to:
1. workflow execution,
2. workflow state mutation,
3. durable control-plane mutation,
4. provider or model invocation, and
5. external side effects.

PCGC-MTH-031: If mechanical evidence for non-interference is incomplete, the verifier MUST expose that limitation as a first-class proof limitation.

PCGC-MTH-032: Orket MUST treat verifier non-interference as a trust-critical proof obligation, not as an implementation detail.

## External Usefulness Requirements

PCGC-USE-001: Orket MUST ship at least one trusted change scope that is not proof-only and not fixture-bounded.

PCGC-USE-002: The first non-fixture trusted change scope MUST solve a task an external engineering or operations team already recognizes as a real unit of work.

PCGC-USE-003: A scope qualifies as externally useful only if all of the following are true:
1. the effect matters outside Orket's own repo,
2. the effect boundary is operationally legible,
3. success and failure outcomes matter to a real evaluator,
4. a deterministic validator or equivalent deterministic check exists, and
5. the workflow can be repeated under the same compare scope without redefining the claim vocabulary.

PCGC-USE-004: Orket MUST provide a canonical evaluator journey for an admitted external scope that lets an evaluator produce or locate the complete evaluation set without repo archaeology:
1. live proof artifact,
2. witness bundle,
3. verifier report,
4. offline claim report, and
5. human-readable evaluator guide.

PCGC-USE-005: The canonical evaluator journey MAY use more than one command or entry point when that separation preserves accepted contract boundaries between live proof and offline inspection.

PCGC-USE-006: External evaluators MUST NOT need repo archaeology to determine what evidence matters.

PCGC-USE-007: For externally useful scopes, Orket MUST ship a deterministic validator library or deterministic validation surface appropriate to the effect class.

PCGC-USE-008: Validator surfaces SHOULD be reusable across multiple trusted change scopes where the effect class is shared.

PCGC-USE-009: Orket SHOULD publish a compare-scope catalog showing for each admitted scope:
1. purpose,
2. effect boundary,
3. validator type,
4. current claim ceiling,
5. currently exposed proof limitations,
6. canonical commands, and
7. forbidden claims.

## Trust Differentiation Requirements

PCGC-TR-001: New trusted change scopes MUST preserve the trust differentiation boundary already governed by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

PCGC-TR-002: Scope admission materials MUST center on claim discipline rather than generic workflow orchestration features.

PCGC-TR-003: Scope admission materials MUST NOT present durable event history, observability volume, human approval surfaces, or control-plane complexity by themselves as the reason to trust workflow success claims.

PCGC-TR-004: For each admitted external scope, Orket MUST be able to show which stronger claims are forbidden and why.

PCGC-TR-005: Orket MUST preserve the distinction between:
1. what the runtime executed,
2. what the witness package records,
3. what the offline verifier accepts,
4. what claim tier is allowed, and
5. what product wording may say publicly.

PCGC-TR-006: New public trust wording for new scopes MUST be promoted separately, must name the compare scope and current claim ceiling, and must not be implied by this document alone.

PCGC-TR-007: Orket MUST NOT advertise broad workflow trust based on a single narrow scope.

## Durable Authority Placement Requirements

PCGC-AUTH-001: Proposal-stage scope exploration MAY begin outside `docs/specs/` while the work remains non-authoritative.

PCGC-AUTH-002: Once a trusted change scope becomes durable authority for admission, publication, or external evaluation, its governing contract family MUST be promoted into `docs/specs/` and reflected through the current authority root governed by `CURRENT_AUTHORITY.md` and repository contribution rules.

PCGC-AUTH-003: A scope MUST NOT remain governed only by `docs/projects/`, `docs/projects/future/`, notes, or proposal folders after it becomes an admitted or externally evaluated authority surface.

PCGC-AUTH-004: Scope catalogs, evaluator guides, and public-trust wording MAY reference exploratory materials, but durable authority MUST resolve to `docs/specs/` for any admitted scope.

## Productization Requirements

PCGC-PROD-001: Orket MUST define a stable artifact family for proof-carrying trusted change scopes.

PCGC-PROD-002: That family MUST preserve shared operator comprehension across scopes while allowing scope-specific validators and contract verdict surfaces.

PCGC-PROD-003: The productized trusted change experience MUST include:
1. an evaluator guide,
2. canonical commands,
3. canonical output locations,
4. machine-readable reports,
5. explicit claim ceilings, and
6. explicit unsupported higher claims.

PCGC-PROD-004: Orket SHOULD standardize a short scope card or equivalent summary surface for each admitted trusted change scope.

PCGC-PROD-005: Scope cards SHOULD be easy to compare side by side.

PCGC-PROD-006: Orket SHOULD provide a stable library or package boundary for deterministic validators, witness helpers, claim verification, and corruption testing used by trusted change scopes.

## Acceptance Requirements

PCGC-ACC-001: A new trusted change scope MUST NOT be called externally admitted until all of the following exist:
1. accepted scope contract,
2. live proof command,
3. witness bundle emission,
4. verifier report,
5. offline verifier report,
6. evaluator guide,
7. corruption coverage for the scope's must-catch set, and
8. separately governed truthful trust wording bounded to that scope.

PCGC-ACC-002: A new scope MUST NOT inherit public claim wording from another scope.

PCGC-ACC-003: If a new scope is proof-only, fixture-bounded, or otherwise adoption-limited, that limitation MUST appear in the guide and in governed public wording.

PCGC-ACC-004: A scope MUST NOT claim `verdict_deterministic`, `replay_deterministic`, or `text_deterministic` above what the offline verifier allows from the actual evidence.

PCGC-ACC-005: Broader product-level trust wording MUST wait until multiple externally meaningful scopes exist and a separate accepted contract defines the cross-scope publication rules.

## Strategic Exit Criteria

PCGC-EXIT-001: This strategic lane is not complete until Orket can truthfully show all of the following:
1. a mechanized trusted-run model covering the current priority invariant and substrate checks,
2. a mechanically justified or mechanically evidenced non-interfering offline verifier boundary,
3. at least one externally useful non-fixture trusted change scope,
4. a catalog of admitted trusted change scopes with truthful claim ceilings, and
5. a clear adoption reason centered on independently checkable bounded workflow success.

PCGC-EXIT-002: The lane is incomplete if Orket still relies on proof-only fixture slices as the main external trust reason.

PCGC-EXIT-003: The lane is incomplete if Orket's adoption story still sounds interchangeable with generic orchestration tools that merely persist workflow history.

## Canonical Strategic Summary

```text
This document does not replace the current trust-reason contract.
It defines the next strategic requirements for extending the admitted
trusted-run foundation into a family of trusted change scopes whose
bounded success claims remain independently checkable.
```

## Acceptance State

These requirements were accepted by the user's explicit request to move this work to a live lane and create an implementation plan on 2026-04-18.

Active execution authority now lives in `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`.
