# Gitea Git long-path bootstrap contract delta

## Summary
- Change title: Enable Git long paths before repository initialization.
- Owner: Orket Core.
- Date: 2026-09-25.
- Affected contract: `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`.

## Delta
- Current behavior: Initialization enables repository-local `core.longpaths` only
  after `git init`. Git for Windows can fail before reaching that configuration.
- Proposed behavior: The adapter's fixed command options enable long paths before
  every subcommand, including initialization. The durable local setting remains.
- Why now: The retained third v0.6.105 campaign passed source but failed nineteen
  installed Windows cases at Git initialization. A real short/long comparison
  reproduced `Filename too long`; the pre-init option repaired the same boundary.

## Migration Plan
1. Compatibility window: No embedding API, journal format or cache relocation.
2. Migration steps: Use the corrected adapter. Preserve existing retained objects,
   export intent and recovery authority; this change grants no retry permission.
3. Validation gates: Real factory/owned Git initialization at a 236-character
   repository path and 249-character objects path, a short positive control,
   physical repository state and durable local configuration. Preserve command
   outcome, privacy, cancellation, descendant and filesystem controls. Fresh frozen
   source and installed Windows matrices remain required for publication.

## Rollback Plan
1. Trigger: Changed command ownership, private failures, finite limits or export
   intent/recovery behavior.
2. Steps: Stop new export admission, preserve evidence and revert this scoped fix.
3. State recovery: Preserve journals and Git objects. Local initialization or
   interruption does not prove remote outcome or authorize another push.

## Versioning Decision
- Version bump type: Compatible pre-1.0 patch within the v0.6.105 candidate.
- Effective version/date: 0.6.105 / 2026-09-25, subject to scoped acceptance.
- Downstream impact: Initialization receives the long-path option before local
  configuration exists. Deadlines, output limits, process owner and error privacy
  remain unchanged. The plan owns exact observations and publication status.

The focused proof exercises local Git and controlled integration paths. It does
not establish remote Gitea, arbitrary deeper paths, every Git distribution, Linux,
fresh installed-package or whole-lane acceptance.
