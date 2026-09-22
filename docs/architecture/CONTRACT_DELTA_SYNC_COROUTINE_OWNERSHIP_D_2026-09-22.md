# Explicit native coroutine owners

## Summary
- Change title: Replace shared daemon coroutine execution with owned native loops
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-22
- Affected contracts: synchronous bridge, SDK model/memory, Piper, review and provider inventory
- Status: Implementation contract; scoped acceptance remains in the canonical plan
- Durable authority: `docs/specs/SYNC_COROUTINE_OWNERSHIP.md`

## Delta
- Before: one global daemon loop survives all callers; blocking future waits are
  permitted on active event loops and there is no bridge shutdown. Provider inventory
  duplicates a separate coroutine helper and leaves refused coroutine objects open.
- After: standalone calls own a complete loop lifetime; resources needing affinity
  use an explicit serialized owner. SDK model generation and HTTP cleanup share that
  owner. Native guards refuse event-loop misuse before work and dispose of unstarted
  coroutine inputs. Caller context is copied for every invocation.
- Close stops admission, drains active work, finalizes the resource on its loop and
  closes loop resources. Cleanup failures remain visible and cannot become successful
  retries. Review and provider command guards precede native observations/effects.

## Migration
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Use owned native workers for synchronous calls from async applications; await
  native async APIs directly where available. Do not block an event loop with the bridge.
- Supply an explicit `SyncCoroutineOwner` when multiple calls share loop-bound
  resources, and close it in the owning lifetime. Calls on one owner are serialized.
- Close SDK model providers through their application/embedding owner. A closed or
  failed owner cannot admit more work; create a new resource instead.
- Keep 0.6.x compatibility exports; no 0.7 cutover is authorized by this change.

## Verification and limits
Require retained counterexamples, actual SQLite/HTTP/Git/process effects, affinity,
fresh contexts, cleanup failure and interruption proof plus installed parity.
Existing tests that expected event-loop blocking migrate to refusal and owned
success assertions. No relaxed deadlines, inferred model acceptance, new inventory
command descendant guarantee, full D acceptance or lane retirement.
