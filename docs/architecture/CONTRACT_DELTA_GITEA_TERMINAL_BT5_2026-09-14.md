# Gitea worker terminal and resource consistency

## Summary
- Change title: Settle renewal and atomically publish Gitea worker closeout.
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contracts: `CONTROL_PLANE_TERMINAL_AUTHORITY.md`, governed start-path
  matrix and `CURRENT_AUTHORITY.md`.

## Delta
- Current behavior: terminal success can survive failed lease release; renewal
  overlaps closeout and local publication errors can dispatch another remote
  final-state write. Seventeen controlled counterexamples reproduce these gaps.
- Proposed behavior: settle renewal first; invoke the selected remote closeout
  once; publish the corresponding local terminal/resource records in one existing
  transaction. Compare retained identities and validate terminal reuse. Execution
  and lease clocks consume explicit providers with canonical default composition.
- Why this break is required now: the combined BT-5 candidate retained completed
  run/attempt records and active leases after a timestamp rejection. Independent
  instrumentation also measured backward UTC with advancing monotonic time.

## Migration Plan
1. Compatibility window: existing stored schemas remain unchanged. Runtime
   composition supplies the transaction owner; embedding construction must bind
   the same store and declared clock inputs.
2. Migration steps: preserve old stores and remote observations. Refuse
   contradictory terminal reuse; no automatic historical repair or remote retry.
3. Validation gates: every closeout write boundary with error/cancellation,
   reversed clocks, renewal ownership, uncertain remote response, healthy/failing
   work, native process interruption, installed Windows/Linux Python 3.11/3.12,
   actual integration flow and the current combined family envelope.

## Rollback Plan
1. Rollback trigger: partial terminal/resource publication, duplicate remote
   closeout, leaked renewal, or invented time/observation authority.
2. Rollback steps: stop affected admission and retain evidence; repair the
   demonstrated predicate without restoring split closeout writes.
3. Data/state recovery notes: SQLite rollback cannot undo remote or filesystem
   effects. Unknown outcomes require reconciliation, not automatic redispatch.

## Versioning Decision
- Version bump type: pending normal commit/release policy; no release performed.
- Effective version/date: 0.6.2 worktree candidate, 2026-09-14.
- Downstream impact: public CLI behavior and stored schemas remain unchanged;
  explicit transaction/clock composition owns the changed local publication path.
