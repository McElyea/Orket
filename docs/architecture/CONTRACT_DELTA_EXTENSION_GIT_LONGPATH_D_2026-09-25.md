# Extension Git long-path contract delta

## Summary
- Change title: Enable long paths before extension clone and later Git commands.
- Owner: Orket Core.
- Date: 2026-09-25.
- Affected contract: `docs/architecture/CONTRACT_DELTA_EXTENSION_INSTALL_D_2026-09-19.md`.

## Delta
- Current behavior: Extension Git commands depend on ambient Git long-path
  configuration. A valid local source can fail clone into its allocated checkout.
- Proposed behavior: The existing `run_git` owner supplies the fixed option
  `-c core.longpaths=true` before every Git subcommand. The setting applies only
  to that invocation; it requires no machine or repository configuration change.
- Why now: The fourth .105 campaign passed 3,460 source cases but failed nine
  installed Windows cases at clone. A fresh actual-manager diagnostic and a real
  integration opening reproduced a successful short install followed by clone
  exit 128 with a captured `Filename too long` classification at a projected
  261-character loose-object path. Historical campaign stderr remains absent.

## Migration Plan
1. Compatibility window: No API, catalog schema, path relocation or wire change.
2. Migration steps: Use the corrected extension Git owner. Preserve all existing
   installed and unpublished checkouts; the change authorizes no retry or deletion.
3. Validation gates: One real SDK source must install at both short and actual
   over-260 Git object paths, preserving exact commit, source content, durable
   catalog row, existing listing defaults and native settlement. Keep the prior
   nine identities and ownership/lifetime/cancellation controls. Fresh frozen
   source and both installed Windows cells remain required for publication.

## Rollback Plan
1. Trigger: Changed resource ownership, operation capture, privacy or settlement.
2. Steps: Drain active installations and restore the scoped command construction.
3. State recovery: Retain every checkout and catalog observation. A failed or
   interrupted attempt does not establish that no local effect occurred.

## Versioning Decision
- Version bump type: Compatible pre-1.0 patch within the v0.6.105 candidate.
- Effective version/date: 0.6.105 / 2026-09-25, subject to scoped acceptance.
- Downstream impact: The existing command supervisor, captured working directory
  and operation environment, repository-environment filtering, terminal-prompt
  refusal, 120s clone and 30s other-command deadlines, bounded capture, cleanup
  classification and private errors remain authoritative.

The canonical plan records exact retained observations and publication status.
Local source diagnostics establish neither remote Git behavior, every Git build
or path depth, installed-wheel acceptance, Linux application acceptance, nor lane
completion. Generic SDK catalog representation drift remains separate D work.
