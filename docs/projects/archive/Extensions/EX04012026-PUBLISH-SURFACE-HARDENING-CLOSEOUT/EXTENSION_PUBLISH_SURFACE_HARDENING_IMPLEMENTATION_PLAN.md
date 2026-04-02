# Extension Publish Surface Hardening Implementation Plan

Last updated: 2026-04-01
Status: Archived
Owner: Orket Core
Lane type: Extension publish surface hardening

## Authority posture

This document is the archived implementation authority record for the completed `Extension Publish Surface Hardening` lane formerly recorded in `docs/ROADMAP.md`.

It picks up only the publish and distribution surface explicitly deferred by the archived package lane.
It does not reopen package-shape, validation-shape, manifest-family, or runtime-authority questions that were already fixed by the Packet 1 package surface.

The archived package-surface lane remains historical closeout under `docs/projects/archive/Extensions/EX04012026-PACKAGE-SURFACE-HARDENING-CLOSEOUT/`.
No separate requirements lane was needed because this publish lane stayed within the decision lock below.

## Source authorities

This plan is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
5. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
6. `docs/guides/external-extension-authoring.md`
7. `docs/templates/external_extension/README.md`
8. `docs/templates/external_extension/.gitea/workflows/ci.yml`
9. `docs/templates/external_extension/.gitea/workflows/release.yml`
10. `docs/projects/archive/Extensions/EX04012026-PACKAGE-SURFACE-HARDENING-CLOSEOUT/CLOSEOUT.md`
11. `docs/projects/future/RUNTIME_OS_FUTURE_LANE_REQUIREMENTS_PACKET.md`

## Purpose

Turn the now-fixed Packet 1 external-extension package surface into one canonical publish story that is:
1. versioned
2. buildable from the supported external extension repository shape
3. publishable through one maintainer path
4. retrievable through one operator intake path
5. still subordinate to host validation and host runtime authority

This lane must answer one cold question:
what exact thing gets published, how is it versioned, and what does an operator do with it before runtime can consider it admissible?

## Decision lock

The lane stays fixed to these points:
1. publish only, not package-surface redesign
2. the Packet 1 external extension package shape remains the current canonical source surface under `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
3. `manifest_version: v0` remains the only admitted manifest family
4. `orket ext validate <extension_root> --strict --json` remains the canonical host-validation path
5. validation success remains admissibility evidence only and does not become publish authority or runtime authority
6. publish hardening must stay within the existing Python package surface rooted at `pyproject.toml` and the canonical external extension repository shape
7. if multiple release artifacts are emitted, exactly one must be designated operator-authoritative for intake and validation; the others are derivative only
8. release automation may be used as proof input, but workflow success is not a second authority source
9. no package registry, marketplace, discovery catalog, or download-product story may silently enter this lane unless explicitly added to the roadmap in a later lane
10. no runtime auto-discovery, auto-execution, or capability-authority broadening may be justified from publish success

## Scope

### 1. One canonical publish artifact story

Define one supported published artifact family for external extensions built from the canonical package surface.

This lane must answer:
what exact artifact does an extension maintainer publish, and which artifact is authoritative for operator intake?

Required outputs:
1. one authoritative published artifact family
2. one explicit rule for any derivative artifact family
3. one canonical mapping from source tree to release artifacts
4. one canonical expectation for manifest inclusion and package metadata inclusion inside the published surface

### 2. One canonical version and release-authority story

Lock one cold version story across:
1. `pyproject.toml`
2. manifest `extension_version`
3. built artifact metadata
4. release tag or release identifier

This lane must answer:
what version markers must agree before a publish is considered truthful?

Required outputs:
1. one canonical version authority rule
2. one canonical tag or release identifier rule
3. one fail-closed outcome for version drift

### 3. One canonical maintainer publish path

Define the minimum maintainer path for publishing a supported external extension.

This lane must answer:
what exact commands or workflow does the maintainer run to build, verify, and publish the admitted artifact?

Required outputs:
1. one canonical local build path
2. one canonical artifact verification path
3. one canonical automation path if automation is admitted
4. one explicit statement of what publish success does and does not mean

### 4. One canonical operator intake path

Define the minimum operator-facing flow after an extension artifact is published.

This lane must answer:
how does an operator retrieve the admitted artifact, stage it into the canonical extension-root shape when required, and prove host admissibility?

Required outputs:
1. one canonical retrieval or staging expectation
2. one canonical path back to `orket ext validate <extension_root> --strict --json`
3. one explicit boundary between published artifact trust and host runtime authority

### 5. One Packet 1 fail-closed publish story

Lock the minimal fail-closed publish expectations, including:
1. failure on version drift between source, manifest, artifact, and release identifier
2. failure when the authoritative published artifact cannot reconstruct or preserve the canonical extension-root validation surface
3. failure when a published artifact drops manifest or entrypoint truth
4. failure when publish docs or tooling imply publish success grants runtime authority

This lane must answer:
what publish-surface drift is rejected now, and what stays explicitly deferred?

## Non-goals

This lane explicitly refuses:
1. package-surface reopening
2. validation-surface redesign
3. package registry or marketplace product design
4. public catalog or discovery UX
5. cloud-hosted extension distribution platform work
6. new manifest families or schema redesign
7. runtime auto-discovery or install-time execution authority
8. API or UI productization of publish flows
9. seam extraction, facade reduction, or repo modularization hidden inside publish ergonomics
10. capability-model broadening beyond the current Packet 1 declaration and validation surface unless the same change proves it is strictly required

## Same-change update targets

At minimum, lane execution must keep these surfaces aligned in the same change when the publish story changes:
1. `docs/ROADMAP.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
4. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
5. `docs/guides/external-extension-authoring.md`
6. `docs/templates/external_extension/README.md`
7. `docs/templates/external_extension/.gitea/workflows/ci.yml`
8. `docs/templates/external_extension/.gitea/workflows/release.yml`

If the publish surface becomes durable enough to stand alone, extract a dedicated canonical publish-surface spec instead of overloading the package or validation specs.

## Proof gates

### Gate 1 - Publish artifact authority proof

Prove the admitted published artifact is a real build product of the canonical external extension package surface.

Required proof:
1. build the admitted artifact family from the canonical external extension source shape
2. inspect artifact metadata for version and package identity alignment
3. prove the authoritative artifact preserves or reconstructs the canonical extension-root validation surface needed for host strict validation

### Gate 2 - Version and release-authority proof

Prove version markers tell one story.

Required proof:
1. `pyproject.toml` version, manifest `extension_version`, and artifact metadata agree
2. the admitted release tag or release identifier agrees with that version
3. version drift fails closed in tooling or automation

The existing `docs/templates/external_extension/.gitea/workflows/release.yml` surface is valid proof input for the tag-version discipline expected here.

### Gate 3 - Canonical maintainer path proof

Prove a maintainer can publish without repo-internal knowledge.

Required proof:
1. build the admitted artifact from the external extension template or a copied external extension fixture
2. run the canonical artifact verification path
3. run the admitted publish automation or its equivalent local path
4. show the maintainer path matches the docs and template wording

### Gate 4 - Canonical operator intake proof

Prove an operator can take the admitted published artifact and return to the host-validation path truthfully.

Required proof:
1. retrieve or stage the authoritative published artifact in a clean environment
2. reconstruct or expose the canonical extension root when required
3. run `orket ext validate <extension_root> --strict --json`
4. keep any required SDK validation or tests aligned with the documented operator or maintainer split

### Gate 5 - Fail-closed publish proof

Prove the publish surface rejects the important drift cases.

Required proof cases:
1. version mismatch across source, manifest, artifact, or release identifier
2. authoritative artifact missing manifest truth
3. authoritative artifact missing or breaking entrypoint truth
4. derivative artifact being mistaken for the operator-authoritative intake artifact
5. docs or tooling wording drifting into "published means trusted to run"

### Gate 6 - No second authority proof

Prove publish hardening does not create runtime authority.

Required proof:
1. published artifacts still require host validation before runtime consideration
2. validated published artifacts still remain subject to host-owned capability and runtime checks
3. no codepath bypasses host governance because a publish step succeeded

## Execution sequence

1. freeze the authoritative published artifact family against the already-fixed package surface
2. align version, tag, and artifact metadata authority
3. align maintainer docs, template docs, template automation, and artifact verification around one publish path
4. prove operator intake returns to the canonical host-validation seam without creating a second authority center
5. close the lane only when publish docs, template, tooling, and artifact truth tell one cold story

## Completion bar

This lane is complete only when:
1. an extension maintainer has one supported publish path
2. an operator has one supported intake path from the published artifact back to strict host validation
3. source version, manifest version, artifact metadata, and release identifier tell one cold story
4. package-surface and validation-surface Packet 1 boundaries remain explicit
5. publish success is visibly subordinate to host validation and runtime authority
6. registry, marketplace, catalog, and discovery concerns are still clearly deferred

## Stop conditions

Stop and narrow immediately if the lane starts absorbing:
1. package registry or marketplace strategy
2. download or discovery product design
3. new manifest-family design
4. runtime authority expansion
5. API or UI productization of publish flows
6. seam extraction or facade reduction
7. package-surface redesign disguised as publish ergonomics
