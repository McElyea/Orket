# SDK, legacy extension and manual review terminal authority

## Summary
- Change title: Atomic terminal publication and validated retained closeout.
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contract: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

## Delta
- Current behavior: interruption can retain success truth and a completed attempt
  beside an executing run. Review failure cleanup can replace the originating error.
- Proposed behavior: the existing application transaction owns terminal writes and
  validates retained family evidence before no-op reuse or result projection.
  Secondary review closeout errors are logged while preserving the original error.
- Why required now: actual SDK, legacy and real Git review counterexamples contradict
  the shared terminal guarantee required by BT-5.3/5.

## Migration Plan
1. Compatibility window: no mixed old/new writers; no permissive compatibility shim.
2. Migration steps: stop older writers and preserve stores and artifacts. Coherent
   histories support read-only reuse. Partial or conflicting histories refuse and
   require separately admitted reconciliation; no backfill or effect redispatch.
3. Validation gates: composed public flows, post-write faults/cancellation, retained
   corruption and competing closeout, copied actual preceding-wheel databases,
   source and installed Windows/Linux Python 3.11/3.12 affected-family regressions.
   The canonical plan records current results and incomplete acceptance predicates.

## Rollback Plan
1. Trigger: a current terminal consistency or required regression predicate fails.
2. Steps: stop affected admission and retain evidence; repair before reopening.
3. Recovery: preserve prior effects. An older writer cannot safely repair a partial
   history. This delta does not grant admission atomicity or automatic recovery.

## Versioning Decision
- Version bump type: patch candidate under the existing core release policy.
- Effective version/date: unreleased 0.6.2 worktree candidate, 2026-09-14;
  release version/tag assignment remains a separate required release gate.
- Downstream impact: explicit transaction factory required for direct service
  construction; package builders provide it. Public result shapes remain stable.
