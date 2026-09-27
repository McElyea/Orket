# Runtime verification inputs and publication ownership

## Summary

- Change title: Capture verification inputs and retain native support publication.
- Owner: Orket Core.
- Date: 2026-09-27.
- Affected contracts: `docs/specs/RUNTIME_VERIFICATION_OWNERSHIP.md`,
  `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`, and the unchanged completion-authority
  ceiling in `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`.

## Delta

- Previous behavior: nested verifier policy and result inputs could change across
  awaits. Support-artifact relative paths resolved on the event loop; metadata and
  file operations could outlive interrupted callers. A syntax worker failure
  during cancellation could be converted into a diagnostic and admit a later
  command.
- Current behavior: each verification invocation detaches consumed policy and
  selects workspace/environment before waiting. Existing native owners retain
  metadata, syntax and path work. Support publication captures its payload and
  owns all three output operations through settlement. Native failure during
  interruption cannot authorize subsequent verification commands. The existing
  stateless process supervisor binds cancellation logs to the selected invocation
  workspace, preserving the same native backend and resource lifetime.
- Why now: the current architectural-truth D2/D3 audit reproduced caller mutation,
  loop blockage and escaped native work on the actual service paths.
- Unchanged: command process ownership/deadlines, result and support schemas,
  completion authority, index tolerance, partial effects and resolved-path limits.
  Preflight clock/Note selection is a separate adjacent change.

## Migration Plan

1. No compatibility shim or wire migration is required. Callers retain the existing
   public signatures and await the operation through cleanup.
2. Set configuration before invoking `verify()`; changing borrowed nested values
   after invocation begins no longer changes its admitted checks. Supply an
   explicit command environment when ambient invocation capture is unwanted.
3. Preserve input/publication ownership regressions in both Quality selections,
   alongside existing verifier, process-lifetime, shutdown, support-history and
   card-acceptance controls. Inspect real handles, child outcomes and retained
   artifacts; injected latency is not a performance benchmark.

## Rollback Plan

1. Trigger: a scoped regression in command semantics or support history.
2. Repair the boundary while retaining input capture and worker ownership; do not
   restore abandoned native operations or mutable admission as a fallback.
3. Existing artifacts remain compatible. Partial publications require inspection;
   cancellation cannot establish rollback, and an index is not a transaction.

## Versioning Decision

- Version bump type: patch.
- Effective version/date: next architectural-truth patch candidate, 2026-09-27.
- Downstream impact: invocation snapshots and longer interrupted cleanup waits;
  no expanded acceptance or containment authority.
