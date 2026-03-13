# RP03122026 0.4.0 Release Process Implementation Plan

Last updated: 2026-03-12
Status: Archived
Owner: Orket Core
Lane type: Priority process hardening

Archive note:
1. Completed and archived on 2026-03-12.
2. Closeout authority: [docs/projects/archive/techdebt/RP03122026/Closeout.md](docs/projects/archive/techdebt/RP03122026/Closeout.md)

Requirements authority:
1. [docs/projects/techdebt/RP03122026/01-REQUIREMENTS.md](docs/projects/techdebt/RP03122026/01-REQUIREMENTS.md)

## Goal

Implement the `0.4.0` release-process requirements as active authority without turning this lane into a UI project or a general documentation rewrite.

This plan delivers the canonical core release policy, the release-gate and proof-report specs, the contributor and authority alignment work, and the bounded docs-freshness cleanup needed to make `0.4.0` a process-backed release milestone.

## Delivery Strategy

1. Lock the durable release/versioning policy first so all later docs align to a stable source of truth.
2. Define the checklist and proof-report artifacts next, because they carry the release gate semantics introduced by the requirements.
3. Align contributor, authority, and index docs only after the durable spec surfaces are in place.
4. Handle stale authority docs and misleading diagrams only to the extent necessary to remove active release/process drift.
5. If broader documentation modernization is required, open a follow-on lane rather than widening this one.

## Workstream 1: Canonical Core Release Policy

Objective:
1. Make `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md` the durable authority for core release/versioning policy.

Actions:
1. Align the spec to the locked requirements for:
   - canonical version authority
   - strict annotated tag format
   - docs-only exemption boundaries
   - minor-version major-project rule
   - proof-mode and proof-result vocabulary
   - compatibility classification fields
   - `0.4.0` transition rule
   - stable release artifact storage locations
2. Ensure the spec clearly excludes SDK versioning authority.
3. Ensure the spec does not imply UI readiness is part of the `0.4.0` milestone.

Deliverable:
1. [docs/specs/CORE_RELEASE_VERSIONING_POLICY.md](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md)

Exit:
1. The spec reflects the requirements without policy drift.

## Workstream 2: Release Gate Checklist

Objective:
1. Create the durable checklist used to evaluate whether a core release satisfies the required gate surfaces.

Actions:
1. Create `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`.
2. Define checklist sections for:
   - version and tag alignment
   - canonical user-surface verification
   - proof-record completeness
   - compatibility classification completeness
   - governance truthfulness review
   - release artifact placement
3. Distinguish patch-release expectations from minor-release expectations where the requirements allow narrower verification.
4. Define how docs-only exempt commits are treated so the checklist does not accidentally impose version bumps where the requirements forbid them.

Deliverable:
1. `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`

Exit:
1. The repo has a stable release gate checklist that maps directly to the locked requirements.

## Workstream 3: Release Proof Report Template

Objective:
1. Create the canonical proof-report template and make release proof storage concrete.

Actions:
1. Create `docs/specs/CORE_RELEASE_PROOF_REPORT.md`.
2. Define the minimum proof-record fields, including:
   - surface name
   - proof mode
   - proof result
   - explicit reason for `blocked`, `not_applicable`, or allowed `structural` use
   - evidence links
3. Define sections for:
   - summary of change
   - stability statement
   - compatibility classification
   - required operator or extension-author action
4. Define the relationship between:
   - `docs/releases/<version>/PROOF_REPORT.md`
   - `benchmarks/results/releases/<version>/`

Deliverables:
1. `docs/specs/CORE_RELEASE_PROOF_REPORT.md`
2. Stable release-proof storage convention reflected in active authority docs

Exit:
1. Minor releases have a canonical report shape and stable artifact locations.

## Workstream 4: Contributor and Authority Alignment

Objective:
1. Remove drift between the durable release policy and active workflow/authority docs.

Actions:
1. Update `docs/CONTRIBUTOR.md` to reference the canonical release/versioning policy and any checklist/report authority that contributors must use.
2. Update `CURRENT_AUTHORITY.md` so the release/versioning process has an explicit canonical path.
3. Update `docs/README.md` so the docs index includes the new durable release surfaces.
4. Update `docs/requirements/sdk/VERSIONING.md` only as needed to preserve the SDK/core boundary without redefining SDK policy.
5. Remove or correct stale active statements that describe `0.4.0` as a frontend-first milestone.

Deliverables:
1. `docs/CONTRIBUTOR.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/README.md`
4. any minimal boundary-alignment edits required in overlapping active docs

Exit:
1. Active authority docs point to the same canonical release-process source of truth.

## Workstream 5: Patch-Bump and Tag Enforcement Path

Objective:
1. Define how the repo will actually enforce the release/versioning rules introduced by the requirements.

Actions:
1. Specify the enforcement mechanism for:
   - patch version bumps on non-exempt `main` commits
   - changelog/version alignment
   - annotated core tag format
2. Decide whether enforcement is:
   - workflow-based,
   - script-based,
   - manual gate backed by a checklist,
   - or a combination
3. Ensure the chosen path can distinguish docs-only exempt commits from non-exempt commits.
4. Keep the enforcement design truthful about what is actually automated versus what remains operator-controlled.

Deliverable:
1. Explicit enforcement approach captured in the active docs/spec surfaces produced by this lane

Exit:
1. The requirements' enforcement clause is no longer implicit.

## Workstream 6: Docs Freshness and Diagram Triage

Objective:
1. Reduce active release/process authority drift without broadening into a general docs rewrite.

Actions:
1. Audit active docs for:
   - stale release framing
   - stale process language
   - misleading support/contact claims
   - diagrams that are visually attractive but operationally unhelpful
2. Update, demote, or remove active diagrams that no longer improve operator or contributor understanding.
3. If the required docs work expands beyond release/process authority, open a separate follow-on lane with explicit closure criteria.

Deliverable:
1. Reduced active-doc drift around release/process authority

Exit:
1. This lane either resolves the active drift or hands broader documentation modernization to a separate explicit lane.

## Verification

Required verification for this planning-and-authority lane:

1. `python scripts/governance/check_docs_project_hygiene.py`
2. source review confirming:
   - roadmap entry points to this plan
   - contributor and authority docs reference the canonical release policy
   - active docs no longer describe `0.4.0` as a frontend-first milestone

Live runtime proof is not a completion requirement for the planning/doc-authority edits themselves.
Live release proof becomes a requirement of the release process defined by this lane, not of the lane's own documentation edits.

## Completion Gate

1. `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md` matches the locked requirements.
2. `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md` exists.
3. `docs/specs/CORE_RELEASE_PROOF_REPORT.md` exists.
4. `docs/CONTRIBUTOR.md`, `CURRENT_AUTHORITY.md`, and `docs/README.md` align to the canonical release-process authority.
5. The release artifact storage rule is explicit and stable.
6. The enforcement path for patch bumps, changelog alignment, and tag format is explicit.
7. Active docs do not describe `0.4.0` as a UI milestone.
8. `python scripts/governance/check_docs_project_hygiene.py` passes.
