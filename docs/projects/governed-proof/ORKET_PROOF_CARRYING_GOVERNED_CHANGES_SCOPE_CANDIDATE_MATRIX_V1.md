# Orket Proof-Carrying Governed Changes Scope Candidate Matrix v1

Last updated: 2026-04-18
Status: Active lane working doc
Owner: Orket Core

Implementation lane: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_IMPLEMENTATION_PLAN.md`
Accepted requirements: `docs/projects/governed-proof/ORKET_PROOF_CARRYING_GOVERNED_CHANGES_REQUIREMENTS_V1.md`

## Purpose

Compare plausible first externally useful trusted change scopes before Workstream 2 chooses one for durable contract extraction and implementation.

## Boundary

This document is a lane-local evaluation surface.

It does not:
1. admit a new trusted change scope,
2. broaden public trust wording,
3. replace a durable scope contract under `docs/specs/`, or
4. guarantee that the current recommendation becomes the final chosen scope.

## Evaluation Criteria

Each candidate is assessed against the same lane-local questions:

1. Is the task meaningful to an external engineering or operations team?
2. Is the effect boundary operationally legible in one short evaluator guide?
3. Does a deterministic validator or equivalent deterministic check already exist or look straightforward?
4. Can the scope reuse the current trusted-run evidence vocabulary without relabeling another scope's evidence?
5. Is the mutation or side-effect risk small enough for a truthful first externally publishable scope?
6. Is the scope likely to produce a clean scope-local publication boundary?

## Candidate Comparison

| Candidate scope | External usefulness | Effect legibility | Deterministic validation path | Reuse of current trusted-run foundation | Mutation risk | Lane recommendation |
|---|---|---|---|---|---|---|
| trusted Terraform plan decision | high | high | high if bounded to stable plan review criteria | medium to high because the repo already carries Terraform reviewer authority under `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md` and `CURRENT_AUTHORITY.md`, though that authority is not itself a governed-proof admission decision | low to medium if bounded to decision publication rather than infra mutation | leading candidate for first detailed investigation |
| trusted repo patch change | medium | high | high | high because it stays close to the current trusted-run shape | medium | strongest fallback or bridge candidate |
| trusted issue creation | medium | high | medium | medium | medium | useful later family member, weaker first flagship |
| trusted config rollout | high | medium | medium | medium | high | not preferred as the first externally publishable scope |
| trusted SQL migration apply | high | medium | medium | low to medium | very high | not preferred as the first externally publishable scope |

## Current Recommendation

The Workstream 2 selection is now:

1. choose `trusted Terraform plan decision` as the first non-fixture scope for durable contract extraction and implementation next, and
2. keep `trusted repo patch change` as the fallback if Workstream 3 uncovers a scope-local proof blocker that the Terraform path cannot clear truthfully.

The superseded lane-local recommendation for Workstream 2 was:

1. investigate `trusted Terraform plan decision` first as the most promising externally useful and evaluator-legible candidate, and
2. keep `trusted repo patch change` as the fallback if the Terraform path cannot achieve a clean scope-local publication boundary.

This is now a lane selection decision for implementation next, not an admitted-scope decision.

## Why Terraform Plan Decision Leads

The current lane-local case for investigating a Terraform plan decision first is:

1. external teams already recognize Terraform plan review as real operational work,
2. plan review criteria can be bounded more cleanly than broad infrastructure mutation,
3. the evaluator story can stay legible if the scope is kept to policy-backed decision publication rather than generic infra governance, and
4. the repo already carries Terraform reviewer authority under `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md` and `CURRENT_AUTHORITY.md`, which may reduce reinvention risk without implying that Terraform is already part of the governed-proof external trust story.

## Why Repo Patch Change Remains The Fallback

Repo patch change remains the best fallback because:

1. it stays close to the current proof-bearing runtime slice,
2. deterministic validation is comparatively straightforward,
3. the mutation boundary can stay small, and
4. it is less likely to force new runtime authority families before the scope-family story is stable.

## Selection Rule For Workstream 2

Workstream 2 should not finalize the first scope until all of the following are true:

1. one candidate has a scope-local validator story that is already believable without repo archaeology,
2. one candidate has a scope-local mutation boundary that can be explained without vague caveats,
3. one candidate can produce a truthful evaluator journey without hiding missing proof obligations, and
4. the chosen scope can be promoted into `docs/specs/` without duplicating or relabeling another scope's authority.

Workstream 2 now considers those conditions satisfied for Terraform plan decision through:

1. `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`, and
2. `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`.
