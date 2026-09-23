# Gitea export native ownership contract delta

## Summary
- Change title: Capture Git inputs and retain export filesystem/process lifetimes.
- Owner: Orket Core.
- Date: 2026-09-22.
- Affected contract: `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`.

## Delta
- Current behavior: Git reads ambient process values after construction; payload
  preparation borrows nested arguments and can outlive cancellation; Git's local
  process loop can return while an orphaned descendant still runs.
- Proposed behavior: Construction captures restricted Git inputs; preparation copies
  arguments and owns native filesystem work; the supplied application command
  supervisor retains the entire admitted process lifetime and reports uncertainty.
- Why now: Identical source and installed v0.6.95 integration controls reproduce
  ten failures with three unchanged controls. Retained Git intent, exact-commit
  recovery, authorization and finite command/output limits remain authoritative.

## Migration Plan
1. Compatibility window: No ambient fallback or compatibility shim.
2. Migration steps: Use native `create_gitea_artifact_exporter` through owned
   construction from async callers. Raw exporter/Git embeddings supply the core
   command port. Reconstruct to change captured process configuration.
3. Validation gates: Actual Git/files/HTTP, interruption and independent SQLite
   controls; disposable Gitea export/recovery with teardown; frozen source and
   installed Windows matrices, canonical dependency/package/retained-proof checks.
   Linux clock and wider acceptance gaps remain open.

## Rollback Plan
1. Trigger: Broken retained intent, export recovery or command privacy/lifetime.
2. Steps: Stop new export admission, retain evidence and revert this scoped change.
3. State recovery: Preserve journal and local Git objects. Confirm remote effects;
   cancellation and local teardown cannot establish remote rollback or retry authority.

## Versioning Decision
- Version bump type: Pre-1.0 patch with explicit raw embedding migration.
- Effective version/date: 0.6.96 / 2026-09-22, subject to scoped acceptance.
- Downstream impact: Required command port, captured inputs and retained cancellation.
