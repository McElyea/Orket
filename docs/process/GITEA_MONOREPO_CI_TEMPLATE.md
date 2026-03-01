# Gitea Local Monorepo CI Template

Last reviewed: 2026-03-01

## Goal
Use a local-first CI workflow in Gitea for a monorepo with independently versioned packages.

This template gives you:
1. Path-scoped package CI jobs.
2. Independent package version stamping via CalVer.
3. Reusable files you can copy to another repo.

## What Was Added
1. Workflow: `.gitea/workflows/monorepo-packages-ci.yml`
2. Package config: `.ci/packages.json`
3. Package config template: `.ci/packages.template.json`
4. Change detector: `scripts/ci/detect_changed_packages.py`
5. CalVer stamper: `scripts/ci/stamp_calver.py`
6. Staged-change version stamper: `scripts/ci/stamp_changed_versions.py`
7. Git hook template: `.githooks/pre-commit`
8. Hook installer: `scripts/ci/install_git_hook.ps1`

## Version Scheme
CalVer is used in this format:
1. `YYYY.MM.DD.devN`
2. `N` is git commit count scoped to the package path.

Example:
1. `2026.03.01.dev42`

This avoids calendar-based major bumps and keeps version generation automatic.

## Local Setup (Current Repo)
1. Configure git to use repo hooks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ci/install_git_hook.ps1
```

2. Validate package-change detection:

```powershell
python scripts/ci/detect_changed_packages.py --config .ci/packages.json --base-ref origin/main
```

3. Preview package version stamp (no file write):

```powershell
python scripts/ci/stamp_calver.py --pyproject pyproject.toml --package-path orket_extension_sdk --dry-run
```

4. Optional manual run of staged-change stamping:

```powershell
python scripts/ci/stamp_changed_versions.py --config .ci/packages.json
```

## Gitea Runner Notes
Use a local/self-hosted runner for this workflow.

Runner requirements:
1. `python` in PATH.
2. `git` in PATH.
3. Network access from runner to your Gitea server.

Repository settings:
1. Actions enabled.
2. A runner assigned to this repo/org.

## How the Workflow Works
1. `detect_changes` compares `origin/main...HEAD`.
2. It selects packages from `.ci/packages.json` whose paths changed.
3. `package_ci` runs only for selected packages.
4. Each selected package does install, test, lint, and CalVer preview.

## Reuse Template in Another Repo
Copy these files into the target repo:
1. `.gitea/workflows/monorepo-packages-ci.yml`
2. `.ci/packages.template.json` as `.ci/packages.json`
3. `scripts/ci/detect_changed_packages.py`
4. `scripts/ci/stamp_calver.py`
5. `scripts/ci/stamp_changed_versions.py`
6. `.githooks/pre-commit`
7. `scripts/ci/install_git_hook.ps1`

Then edit `.ci/packages.json`:
1. Set each package `id`.
2. Set each package `path`.
3. Set package `pyproject`.
4. Set package-specific install/test/lint commands.

## Recommended Next Repo Layout
For cleaner independent packaging, migrate to:
1. `packages/orket/pyproject.toml`
2. `packages/orket-sdk/pyproject.toml`

When you do that, update `.ci/packages.json` paths and commands accordingly.

## Troubleshooting
1. No packages detected:
   - Confirm changed file paths match `path` entries in `.ci/packages.json`.
   - Confirm `origin/main` exists in runner checkout.
2. Version stamp fails:
   - Confirm `pyproject` file exists.
   - Confirm `[project]` and `version = "..."` are present.
3. Hook did not run:
   - Confirm `git config core.hooksPath` returns `.githooks`.
