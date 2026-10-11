# 0.8.7: Gardener installation documentation

Date: 2026-10-10 (America/Denver)
Status: Scoped documentation verification complete.

## What changed

Incorporated the installation feedback from Rev 4 of
`V:/Downloads/orket-gardener-field-report (3).html`, SHA-256
`1952d22dabc851896a454e41a8e6be6d61cb1eb01c2da069d36999eb88bf3530`.
The report describes Daniel's setup and observations through core 0.8.4.

The Gardener guide now walks through a source checkout and editable core/SDK
installation, the separately committed trusted example, launcher configuration,
catalog selection, explicit provider selection and upgrade checks. The report
example owns the reusable copy/commit/validate/install recipe; the runbook and
docs index link to it through the Gardener guide. The authority index preserves
the existing canonical installation command and points to the expanded recipe.

The budget example pairs 30000 input and 2048 output with a 32768 host profile.
It distinguishes the command harness's inherited environment from the headless
extension's running API host. Field timing and estimate/token ratios are labeled
observations, not portable sizing or quality guarantees. An unchanged earlier
example remains usable when release notes explicitly state compatibility.

No runtime, SDK, provider, admission or completion behavior changed. The core
patch bump and changelog follow the repository's per-commit release policy.

## What was verified

**Live installation: fallback / success.** A fresh WSL Ubuntu 24.04 workspace
executed the two documentation Bash install blocks, with only their destination
paths relocated under a unique `/tmp` directory and a local Git proof identity.
It cloned public Orket at `ab4f825e1b160ae440fb072d475bcc3a173af4f5`, created a
new environment and installed editable core **0.8.6** plus SDK **0.8.0** using
the documented extras. Dependency checks, version/origin/path checks, real Git
commit, strict extension validation, installation and listing succeeded.
The installed module origin was the new checkout, not the developer workspace.
The catalog selected `example.structured-report` at source commit
`681d334000179710b3ecc4aa108bc50ffa28ed59`.

The upgrade check copied the revised example README, committed it and repeated
strict validation and installation. Validation reported zero errors/warnings;
the catalog selected the new commit
`4ca9fbdd57097d8d3e32f11d020b158c179a4610`, with matching installed README bytes.
Both command producers retain owned-process results, stdout/stderr hashes and
settlement. Routine verification used `ORKET_DISABLE_SANDBOX=1`; no model server
or Docker sandbox was launched.

**Structural configuration: success.** The documented Bash launcher exported
the exact Python/wrapper paths that Gardener's shell-style splitting expects,
and the catalog existed. The actual installed prompt policy resolved the
operator Qwen profile at 32768 context with 30000 input and 2048 output. This
does not prove model/server capacity or inference. Local Markdown link targets,
documentation hygiene, generated authority/check, release policy and whitespace
checks passed. Runtime/source package code is unchanged from the installed
0.8.6 baseline; a fresh 0.8.7 package is not claimed.

Retained evidence:

- `.tmp/gardener-rev4/install.json`; Windows logs/receipt under
  `C:/Users/jonmc/AppData/Local/Temp/orket-gardener-rev4-install-9dxo_g_9`;
  Linux workspace `/tmp/orket-gardener-rev4-install-9dxo_g_9`.
- `.tmp/gardener-rev4/upgrade.json`; logs/receipt under
  `C:/Users/jonmc/AppData/Local/Temp/orket-gardener-rev4-upgrade-ggxq3wo7`.

Both stable receipts use the shared diff ledger and bind the reviewed guide
bytes. No new committed tests were needed for this documentation-only change.

## What was not verified

No new model inference, full Gardener audit, scheduler execution, private rubric,
native Mac/Windows Gardener acceptance, full Orket test suite or fresh 0.8.7
distribution. Historical field timings and quality findings were not rerun.
The existing [27B proof](../0.8.5/PROOF_REPORT.md) retains its original candidate
and limitations. No registry publication is claimed.

## Remaining blockers or drift

No blocker to the requested documentation update. Model suitability, capacity
and report accuracy still require operator verification. The integration stays
report-only and advisory. Whole-runtime live acceptance remains unestablished.

## Exact files touched

- `CHANGELOG.md`
- `CURRENT_AUTHORITY.md`
- `docs/README.md`
- `docs/RUNBOOK.md`
- `docs/architecture/current_authority.json`
- `docs/releases/0.8.7/PROOF_REPORT.md`
- `examples/gardener_harness/README.md`
- `examples/governed-report/README.md`
- `pyproject.toml`
