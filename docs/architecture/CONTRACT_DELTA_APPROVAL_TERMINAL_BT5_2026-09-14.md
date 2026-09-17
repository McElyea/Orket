# Approval denial terminal transaction

## Summary
- Change title: Route both governed approval consumers through atomic closeout.
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contracts: `CONTROL_PLANE_TERMINAL_AUTHORITY.md`, `CURRENT_AUTHORITY.md`.

## Delta
- Previous behavior: denial bypasses the existing transaction wrapper and may
  retain failed run/attempt/truth records while its lease remains active.
  Terminal shortcuts can accept missing truth or unreleased authority.
- New behavior: same-store transaction composition owns the child reads, retained
  tool-step count and terminal/resource writes. Reentry validates the terminal
  join and resource closure before accepting the finished child.
- Reason: actual failed combined-gate history and post-write failure/cancellation,
  reversed-clock and contradictory-history controls demonstrate these gaps.

## Migration Plan
1. Stored schemas remain unchanged. Both application consumers require explicit
   transaction composition; embeddings must bind the existing store.
2. Preserve old histories. Contradictory terminal records refuse continuation;
   this change neither repairs them nor authorizes redispatch.
3. Verify real ASGI decision and restarted epic paths, native model-recovery
   fixture teardown, source/installed family regression and actual provider flow.

## Rollback Plan
1. Stop affected admission and retain evidence if partial closeout or false
   finished-child acceptance recurs. Restore no permissive split-write fallback.
2. Operator intent, epic claims and physical effects retain their separate
   authority. Child rollback does not undo them or authorize unsupported recovery.

## Versioning Decision
- Effective version: 0.6.2 worktree candidate; no release performed.
- Public response schemas and existing recovery ceilings remain unchanged.
- Normal version/changelog/tag policy applies when committing the accumulated work.
