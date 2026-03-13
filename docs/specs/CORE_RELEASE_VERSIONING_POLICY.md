# Core Release Versioning Policy

Last updated: 2026-03-12
Status: Active
Owner: Orket Core

Canonical policy for core engine versioning, release framing, release proof, and release-gate expectations.

This policy governs the core Orket engine only.
SDK versioning remains separately governed by [docs/requirements/sdk/VERSIONING.md](docs/requirements/sdk/VERSIONING.md).

## 1. Canonical Sources

1. Core engine version source of truth: `pyproject.toml` under `[project].version`.
2. Core engine release history source of truth: `CHANGELOG.md`.
3. Contributor workflow authority for release/versioning execution: `docs/CONTRIBUTOR.md`.
4. Current authority snapshot pointer: `CURRENT_AUTHORITY.md`.
5. Core release gate checklist: `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`.
6. Core release proof report template: `docs/specs/CORE_RELEASE_PROOF_REPORT.md`.

## 2. Effective Versioning Model Beginning With `0.4.0`

1. Starting with core engine version `0.4.0`, every commit merged into `main` must bump the core engine patch version unless it qualifies for the docs-only exemption in this policy.
2. Minor version bumps occur only after completion of a roadmap-tracked major project.
3. A major project for core versioning purposes is a roadmap-tracked body of work whose completion materially changes runtime behavior, operator workflows, release governance, or public interfaces.
4. Major-project completion requires:
   - roadmap lane closure,
   - acceptance criteria satisfied, and
   - release contract draft exists.
5. `0.4.0` is reserved for the first process-backed release milestone after release/versioning, proof-gate, compatibility, and docs-authority hardening. It is not reserved for a UI milestone.
6. UI work remains deferred until a separate requirements-backed lane defines truthful UI needs from the internal product surface actually built.

## 3. Tag Format and Alignment

1. Core engine releases must use annotated Git tags in the form `v<major>.<minor>.<patch>`.
2. The tagged commit must match:
   - `pyproject.toml` core version,
   - the top matching version entry in `CHANGELOG.md`, and
   - the intended release boundary described by the release notes or closeout.
3. Do not create a core release tag that claims a version not present in `pyproject.toml`.
4. Earlier descriptive or nonconforming tags are historical exceptions and do not establish precedent for future core-engine releases.

## 4. Canonical User Surface

The canonical user surface used for release verification is the install/runtime/test command set documented in `docs/CONTRIBUTOR.md` and `CURRENT_AUTHORITY.md`:

1. canonical install command
2. default runtime entrypoint
3. API runtime entrypoint
4. canonical test command

Alternative commands may exist, but they must be documented as secondary or explicitly unsupported for release gating.

## 5. Patch Release Discipline

1. Every commit merged into `main` must increment the core engine patch version unless it qualifies for the docs-only exemption.
2. A commit qualifies for the docs-only exemption only if it modifies documentation files exclusively and introduces no runtime, configuration, dependency, packaging, or release-artifact changes.
3. Documentation-only commits are limited to:
   - files under `docs/`
   - root-level `*.md` files
4. All non-exempt commits must:
   - increment the patch version in `pyproject.toml`, and
   - create or update the matching top version entry in `CHANGELOG.md` for that exact released version.
5. Revert commits follow the same rule as normal commits.

## 6. Minor Release Proof Gates

Use `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md` to evaluate minor-release readiness and `docs/specs/CORE_RELEASE_PROOF_REPORT.md` for the canonical report shape.

Before declaring a core minor release ready, produce proof records for:

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
2. the surface is outside the supported scope of that release.

The reason for `not_applicable` must be explicitly recorded in the release proof report.
`not_applicable` must not be used to bypass required proof of an existing supported surface.

## 7. Release Artifact Storage

1. Completed narrative release proof reports must be stored under `docs/releases/<version>/`.
2. `<version>` uses the plain release number, not the Git tag form.
3. Each minor release must produce a proof report using the canonical template in `docs/specs/CORE_RELEASE_PROOF_REPORT.md`.
4. The completed report must be stored as `docs/releases/<version>/PROOF_REPORT.md`.
5. Machine-readable results or bulky supporting evidence, including logs, screenshots, execution traces, or integration evidence, must be stored under `benchmarks/results/releases/<version>/`.

## 8. Compatibility and Release Contract

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

Every minor release must include release notes that contain at minimum:

1. summary of change
2. stability statement
3. compatibility classification
4. required operator or extension-author action

## 9. Documentation Truthfulness

1. Active docs must not describe a future release using stale framing once authoritative direction changes.
2. Public docs must not claim support channels, contact surfaces, or operational guarantees that do not exist.
3. Release policy, license docs, README positioning, and governance language must remain consistent and non-misleading.
4. Diagrams in active docs must improve operator or contributor understanding. Decorative or stale diagrams should be updated, demoted, or removed from active authority surfaces.

## 10. Enforcement Model

1. Core release/versioning enforcement is currently manual and checklist-backed.
2. Until a dedicated core-engine release workflow or tag/version guard is explicitly adopted, Orket Core must enforce:
   - non-exempt patch version bumps on `main`
   - `CHANGELOG.md` and `pyproject.toml` alignment
   - annotated core tag format
   - minor-release proof report completeness
3. Docs-only exemption decisions are made by changed-surface review against this policy and `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`.
4. Existing CI runs or supporting scripts may provide evidence, but they do not replace the canonical release gate unless a later policy update explicitly says they do.

## 11. Authority Roles and Boundaries

1. Final authority for release policy, compatibility classification, and proof-gate acceptance resides with Orket Core.
2. Core engine release policy must not override or redefine SDK-specific versioning authority.
3. SDK versioning remains governed by SDK-specific policy.

## 12. Transition and Change Control

1. The release policy defined in this document governs the `0.4.0` release and all subsequent releases.
2. Earlier releases are historical and are not retroactively required to conform.
3. If this policy changes, update `docs/CONTRIBUTOR.md`, `CURRENT_AUTHORITY.md`, and any overlapping active docs in the same change unless explicitly directed otherwise.
4. Do not let SDK versioning rules drift into core engine versioning authority or vice versa.
