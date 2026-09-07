# Contract Delta: Architectural Truth Slice A

## Summary

- Change title: Failure must fail
- Owner: Orket Core
- Date: 2026-07-29
- Affected contracts:
  - `CURRENT_AUTHORITY.md` runtime entrypoints
  - `docs/CONTRIBUTOR.md` canonical commands
  - `pyproject.toml` installed console scripts and package data
  - governed-action quickstart CLI behavior
  - governed-run default demo resource resolution

## Delta

- Current behavior:
  - the canonical `python main.py` path can print a fatal first-run `SettingsBridgeError` and exit `0`;
  - first-run onboarding calls the synchronous settings bridge from the active event loop;
  - `orket-quickstart --help` enters the approval prompt and noninteractive EOF produces a traceback;
  - `orket demo governed-run` resolves its default scenario from the caller's current directory;
  - the installed `orket` command and source-only card runtime remain separate operator surfaces.
- Proposed behavior:
  - fatal CLI outcomes return a nonzero process exit;
  - first-run persistence executes outside the active event loop and success narration follows verified persistence;
  - the quickstart exposes normal help, explicit scripted decision input, and structured noninteractive failure;
  - the governed-run default scenario is an installed package resource independent of current working directory;
  - Slice A documents the installed/source entrypoint split truthfully while the later convergence work remains active.
- Why this break is required now:
  - process success on fatal failure violates runtime truth and makes automation unsafe;
  - checkout-relative defaults make an advertised installed command unusable from normal operator locations;
  - the current quickstart lacks a stable command-line contract.

## Migration Plan

1. Compatibility window:
   - `python main.py`, `orket`, and `orket-quickstart` remain available during Slice A;
   - no new compatibility alias is introduced;
   - root-command convergence remains a later bounded change under the active plan.
2. Migration steps:
   - propagate an integer result from the async CLI to `main.py`;
   - run synchronous onboarding through a worker thread until the settings surface is natively async;
   - add quickstart argument parsing and EOF handling;
   - add the governed-run default YAML to package data and resolve it through package resources;
   - update runtime authority and operator docs in the same change.
3. Validation gates:
   - native subprocess tests for successful and failed exits;
   - quickstart help, denial, and EOF tests;
   - governed-run demo execution from outside the checkout;
   - canonical pytest and documentation hygiene.

## Rollback Plan

1. Rollback trigger:
   - first-run persistence regresses, a previously successful supported CLI path returns nonzero, packaged default resources cannot be resolved, or teardown leaks runtime resources.
2. Rollback steps:
   - revert the bounded Slice A code and documentation changes together;
   - restore prior console-script/package-data metadata;
   - keep the architectural-truth lane active with the failed proof recorded.
3. Data/state recovery notes:
   - Slice A does not migrate durable schemas;
   - first-run settings remain at the existing canonical path;
   - governed-run demo outputs remain under the caller-selected workspace.

## Implementation State

- Implemented on 2026-07-29:
  - `run_cli()` returns an integer result and `main.py` propagates nonzero outcomes;
  - synchronous first-run checks execute in a worker thread, and onboarding narration follows settings persistence;
  - `orket-quickstart` supports `--help`, `--decision approve|deny`, `--workspace`, and structured EOF refusal;
  - the governed-run default YAML ships as `orket.quickstart` package data and resolves independently of CWD;
  - end-to-end subprocess and outside-checkout tests cover the changed public behavior.
- Still active:
  - installed `orket` and source `python main.py` command convergence;
  - Workstream 1 acceptance remains open until that command-root convergence and
    its installed-runtime proof are complete;
  - repo-wide Ruff remains red and is carried as `AT-EX-015`, while the bounded
    Slice A files are Ruff-clean.

## Versioning Decision

- Version bump type: Patch when the Slice A implementation commit is prepared
- Effective version/date: Pending implementation closeout
- Downstream impact: CLI automation must begin relying on nonzero fatal exits; installed demos gain current-working-directory-independent defaults
