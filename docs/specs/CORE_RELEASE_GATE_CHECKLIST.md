# Core Release Gate Checklist

Last updated: 2026-03-13
Status: Active
Owner: Orket Core

Canonical release gate checklist for core engine releases beginning with `0.4.0`.

Use with:
1. [docs/specs/CORE_RELEASE_VERSIONING_POLICY.md](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md)
2. [docs/specs/CORE_RELEASE_PROOF_REPORT.md](docs/specs/CORE_RELEASE_PROOF_REPORT.md)
3. [docs/CONTRIBUTOR.md](docs/CONTRIBUTOR.md)

## 1. Applicability

1. This checklist applies to core engine release decisions beginning with `0.4.0`.
2. Every post-`0.4.0` commit kept on `main` is a versioned core release step and requires a core version bump plus the matching release tag on that exact commit.
3. Patch releases must satisfy Sections 2 and 3.
4. Minor releases must satisfy Sections 2, 3, and 4.

## 2. Per-Commit Release Discipline

Each governed commit must satisfy all of the following:

1. The commit advances the core engine version.
2. The matching top `CHANGELOG.md` entry exists for that exact version.
3. The matching annotated Git tag `v<version>` exists on that exact commit.
4. The release step is a patch increment unless the commit is a policy-permitted minor or major release step.

## 3. Base Gate for Versioned Core Releases

### 3.1 Version and changelog alignment

1. `pyproject.toml` declares the intended core engine version.
2. The top matching `CHANGELOG.md` entry exists for that exact version.
3. The release boundary is described truthfully in the changelog or release notes.
4. For a commit that is not a policy-permitted minor or major release step, the required patch bump is present in `pyproject.toml`.

### 3.2 Tag alignment

1. The release tag is annotated.
2. The release tag uses the form `v<major>.<minor>.<patch>`.
3. The release tag version matches `pyproject.toml` and `CHANGELOG.md`.
4. The release tag points to the intended release commit.

### 3.3 Canonical user surface authority

1. The canonical install command is explicitly documented.
2. The default runtime entrypoint is explicitly documented.
3. The API runtime entrypoint is explicitly documented.
4. The canonical test command is explicitly documented.
5. Overlapping active docs do not conflict on those surfaces.

### 3.4 Release contract completeness

1. Release notes include a summary of change.
2. Release notes include a stability statement.
3. Release notes include `compatibility_status`.
4. Release notes include `affected_audience`.
5. Release notes include `migration_requirement`.
6. Release notes include required operator or extension-author action, or explicitly state that none is required.

### 3.5 Governance truthfulness

1. Public docs do not claim support channels or contact surfaces that do not exist.
2. Public docs do not claim operational guarantees that do not exist.
3. Active docs do not use stale UI-milestone framing for `0.4.0`.
4. Release policy, license docs, README positioning, and governance language remain consistent and non-misleading.

### 3.6 Release artifact placement

1. If a narrative proof report exists, it is stored under `docs/releases/<version>/`.
2. If machine-readable or bulky supporting evidence exists, it is stored under `benchmarks/results/releases/<version>/`.
3. Storage paths use the plain release number, not the Git tag form.

## 4. Minor Release Additional Gate

1. The release corresponds to a completed roadmap-tracked major project.
2. Release notes summarize the completed major project.
3. A completed proof report exists at `docs/releases/<version>/PROOF_REPORT.md`.
4. The proof report includes required records for:
   - the default runtime entrypoint
   - the API runtime entrypoint
   - at least one real workflow path
   - currently material integration routes
5. Each proof record includes:
   - `surface_name`
   - `surface_type`
   - `proof_mode`
   - `proof_result`
   - `reason` when `proof_mode` is `structural` or `proof_result` is `blocked` or `not_applicable`
   - evidence links
6. `not_applicable` is used only for a missing or out-of-scope supported surface and includes an explicit reason.
7. `structural` is used only where the canonical release policy permits it and includes an explicit reason.
8. Supporting evidence paths are stable and use the release artifact storage locations defined by policy.
9. Final proof-gate acceptance is recorded by Orket Core.
