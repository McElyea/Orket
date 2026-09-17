# Versioned turn dispatch admission

## Summary
- Change title: Refuse ambiguous unversioned turn continuation.
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contract: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

## Delta
- Previous behavior: An old interrupted turn with no step/effect records could
  resume from its accepted checkpoint and execute an already performed tool again.
- New behavior: New admission binds `turn_tool.dispatch_intent.v1` in the existing
  immutable configuration snapshot. Unfinished execution and closure require the
  exact declaration and matching snapshot/payload/run digests. Missing, unsupported
  or unbound declarations refuse without repairing history. Coherent completed
  histories retain existing verified reuse; conflicting truth references refuse.
- Reason: A copied store actually produced by the old wheel demonstrates that
  absent records alone cannot establish pre-effect authority.

## Migration Plan
1. No automatic compatibility window for unversioned unfinished turns. Stop old
   writers and preserve the database, native ownership files and effect artifacts.
2. Refusal while retaining evidence is the supported disposition. Do not stamp old
   runs with the new declaration. A separately admitted reconciliation path remains
   necessary for unknown outcomes; this change does not provide one.
3. Gates: current source and installed composed flows, copied actual old-wheel
   histories, denial/recovery/dispatch boundaries, fresh pre-effect recovery,
   coherent completed reuse and contradictory terminal-reference refusal.

## Rollback Plan
1. Trigger: Any unsupported continuation, false terminal claim or regression in
   declared current flows.
2. Stop admission and preserve failed observations. Do not restore a permissive
   older writer as a recovery mechanism.
3. No historical rewriting, backfill or synthesized effect is part of rollback.

## Versioning Decision
- Contract version: `turn_tool.dispatch_intent.v1` in resolved configuration.
- Effective candidate: unreleased core 0.6.2 worktree, 2026-09-14.
- Downstream impact: Unversioned unfinished turns are refused, including history
  from the intermediate marker-writing implementation. No package release, commit,
  tag or mixed-version writer support is implied.
