# RP03122026 0.4.0 Release Process Requirements

Last updated: 2026-03-12
Status: Archived
Owner: Orket Core
Lane type: Priority process hardening

Archive note:
1. Completed and archived on 2026-03-12.
2. Closeout authority: [docs/projects/archive/techdebt/RP03122026/Closeout.md](docs/projects/archive/techdebt/RP03122026/Closeout.md)

## 1. Objective

Establish the release, versioning, verification, compatibility, and documentation-authority process required to move Orket to `0.4.0` without using a UI milestone as a proxy for maturity.

This lane defines the authoritative core-engine release process beginning with `0.4.0`.

## 2. Scope and Non-Goals

### Scope

This lane establishes process authority for:

1. core engine versioning
2. release tagging and changelog alignment
3. release proof gates
4. compatibility and migration communication
5. governance truthfulness in public docs
6. durable release policy documentation

Additional scope rules:

1. `0.4.0` is governed by the process defined in this document.
2. `0.4.0` is not a UI milestone.
3. UI readiness is not a release milestone.
4. If additional release blockers are discovered during this work, they must be captured in this lane or in a linked follow-on lane with explicit closure criteria.

### Non-Goals

This lane does not:

1. introduce or expand UI requirements
2. redesign SDK release/versioning policy except where boundary alignment is required
3. perform broad documentation modernization unrelated to release/process authority
4. introduce new product capability unrelated to release correctness

Broad documentation modernization may be captured as a separate follow-on lane. Refresh of stale authority docs and misleading operational diagrams remains in scope here.

## 3. Definitions

### Major Project

A roadmap-tracked body of work whose completion materially changes runtime behavior, operator workflows, release governance, or public interfaces.

Completion requires:

1. roadmap lane closure
2. acceptance criteria satisfied
3. release contract draft exists

### Workflow Path

A concrete runtime path representing a real operator or system workflow exercised during release verification.

### Integration Route

A currently material integration surface between Orket and an external component or extension system.

### Proof

Evidence that a required proof surface was evaluated and produced a recorded verification outcome.

### Proof Mode

The verification method used to evaluate a required proof surface.

### Proof Result

The recorded outcome of a proof attempt for a required proof surface.

### Blocked Proof

A proof requirement that could not be completed due to a known external or environmental limitation, where the blocking cause is explicitly documented.

### Active Docs

Documentation surfaces that represent the current authoritative operational description of the system.

### Stale Authority Docs

Documentation that previously held authority but no longer accurately reflects system behavior or policy.

## 4. Normative Release Policy

### 4.1 Version Authority

The canonical source of the core engine version is `pyproject.toml`.

Release tags and `CHANGELOG.md` entries must match the version declared there.

### 4.2 Tag Format

Core engine releases must use annotated Git tags in the following format:

`v<major>.<minor>.<patch>`

Example:

`v0.4.0`

Earlier descriptive or nonconforming tags are historical exceptions and do not establish precedent for future core-engine releases.

### 4.3 Canonical User Surface

The following user surfaces must be explicitly documented and used as the authoritative commands for release verification:

1. canonical install command
2. default runtime entrypoint
3. API runtime entrypoint
4. canonical test command

These commands define the supported operational surface for release gating and verification.

Alternative commands may exist but must be either:

1. documented as secondary, or
2. explicitly marked unsupported for release gating

### 4.4 Patch Version Rule

Every commit merged into `main` must increment the core engine patch version.

Exception:

A commit may be exempt only if it modifies documentation files exclusively and introduces no runtime, configuration, dependency, packaging, or release-artifact changes.

Documentation-only commits are limited to:

1. files under `docs/`
2. root-level `*.md` files

All non-exempt commits must:

1. increment the patch version in `pyproject.toml`, and
2. create or update the matching top version entry in `CHANGELOG.md` for that exact released version

Revert commits follow the same rule as normal commits.

The version increment must occur as part of the merge result.

The enforcement mechanism is defined by the implementation plan.

### 4.5 Minor Version Rule

Minor version increments require completion of a roadmap-tracked major project.

A minor release must include a summary of the completed major project.

### 4.6 Release Proof Requirements

Minor releases must produce proof records for:

1. the default runtime entrypoint
2. the API runtime entrypoint
3. at least one real workflow path
4. currently material integration routes

Each required proof record must contain both `proof_mode` and `proof_result`.

Allowed `proof_mode` values:

1. `live`
2. `structural`

`live` means the required surface was exercised through runtime execution.

`structural` means the required surface was evaluated through non-runtime structural verification explicitly allowed by the canonical release policy.

Allowed `proof_result` values:

1. `success`
2. `blocked`
3. `not_applicable`

`blocked` proofs must include an explicit reason.

`not_applicable` may be used only when:

1. the surface does not exist for the release, or
2. the surface is outside the supported scope of that release

The reason for `not_applicable` must be explicitly recorded in the release proof report.

`not_applicable` must not be used to bypass required proof of an existing supported surface.

### 4.7 Compatibility Classification

Release notes must classify compatibility using three fields.

`compatibility_status` must be one of:

1. `preserved`
2. `breaking`
3. `deprecated`

`affected_audience` must be one of:

1. `operator_only`
2. `extension_author_only`
3. `internal_only`
4. `all`

`migration_requirement` must be one of:

1. `none`
2. `required`

### 4.8 Release Contract Requirements

Every minor release must include release notes that contain at minimum:

1. **Summary of change** - high-level description of what the release introduces or modifies.
2. **Stability statement** - explicit statement of which system surfaces are considered stable.
3. **Compatibility classification** - using the defined compatibility fields.
4. **Required operator or extension-author action** - migration steps or operational changes required after upgrade.

These elements form the minimum release contract communicated to operators and extension authors.

### 4.9 Governance Truthfulness

Public documentation must not present support channels, contact surfaces, or operational guarantees that do not actually exist.

Release policy, license docs, README positioning, and governance language must remain consistent and non-misleading.

### 4.10 Authority Roles

Final authority for release policy, compatibility classification, and proof-gate acceptance resides with Orket Core.

### 4.11 SDK Boundary

Core engine release policy must not override or redefine SDK-specific versioning authority.

SDK versioning remains governed by SDK-specific policy.

### 4.12 `0.4.0` Transition Rule

The release policy defined in this document governs the `0.4.0` release and all subsequent releases.

Earlier releases are considered historical and are not retroactively required to conform.

## 5. Required Durable Outputs

Completion of this lane must produce the following artifacts.

### Canonical release policy

`docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`

This document becomes the long-lived authority for release and versioning rules.

### Release gate checklist

`docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`

### Release proof report template

`docs/specs/CORE_RELEASE_PROOF_REPORT.md`

### Contributor authority alignment

`docs/CONTRIBUTOR.md`

### Authority snapshot alignment

`CURRENT_AUTHORITY.md`

### Release policy reference surface

`docs/README.md`

### Release proof artifact storage

Completed narrative release proof reports must be stored under:

`docs/releases/<version>/`

`<version>` must use the plain release number, for example `0.4.0`, not the Git tag form.

Each minor release must produce a proof report using the canonical template:

`docs/specs/CORE_RELEASE_PROOF_REPORT.md`

The completed report must be stored as:

`docs/releases/<version>/PROOF_REPORT.md`

Example:

`docs/releases/0.4.0/PROOF_REPORT.md`

Machine-readable results or bulky supporting evidence, including logs, screenshots, execution traces, or integration evidence, must be stored under:

`benchmarks/results/releases/<version>/`

The implementation plan may define automation or CI workflows that generate or validate these artifacts, but the storage locations must remain stable.

### Roadmap tracking

The roadmap must track this work and link the canonical implementation plan.

## 6. Acceptance

Acceptance is achieved when all of the following are true.

### Policy Closure

The following policy decisions are explicitly defined in durable documentation:

1. canonical version authority
2. tag syntax
3. canonical user surfaces for release verification
4. patch version rule, including exemption boundaries and update obligations for non-exempt commits
5. minor version rule
6. major-project definition
7. proof mode vocabulary
8. proof result vocabulary
9. compatibility classification fields and vocabulary
10. release contract minimum content
11. authority roles
12. SDK boundary rule
13. `0.4.0` transition rule
14. release proof artifact storage rules

### Durable Authority

A canonical release/versioning policy exists under:

`docs/specs/`

### Documentation Alignment

1. contributor and authority documentation reference the canonical release policy
2. overlapping documentation no longer conflicts with the release policy
3. active docs do not describe `0.4.0` as a frontend-first milestone

### Documentation Freshness

The lane defines explicit follow-through for refreshing stale authority docs and addressing operationally misleading diagrams.
