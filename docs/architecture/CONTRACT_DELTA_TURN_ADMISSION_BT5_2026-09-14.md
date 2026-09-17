# Atomic ordinary turn admission

## Summary
- Change title: Commit ordinary governed turn admission as one record set.
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contracts: `CONTROL_PLANE_TERMINAL_AUTHORITY.md`, governed start-path
  matrix, `CURRENT_AUTHORITY.md`.

## Delta
- Current behavior: policy/configuration, run/attempt and namespace authority
  writes commit separately. Fourteen retained interruption controls leave partial
  authority after failed admission.
- Proposed behavior: admission and state reads use the existing transaction
  factory and borrowed execution/publication ports. All 11 write positions commit
  together or roll back. Resume uses the existing recovery algorithm in that same
  transaction. One shared context preserves committed reconciliation refusal.
- Why this break is required now: BT-5.3/5 requires truthful common admission;
  retaining half an admitted execution contradicts that predicate.

## Migration Plan
1. Compatibility window: no alternate or mixed-writer guarantee is introduced.
2. Migration steps: use the candidate for new admissions while preserving all
   earlier stores and failure evidence. Historical partial or unmarked attempts
   remain subject to explicit reconciliation; this change does not rewrite them.
3. Validation gates: original counterexamples, every write position with error
   and cancellation, native process death before/after commit, recovery refusal
   and ownership regressions, installed Windows/Linux Python 3.11/3.12, and actual
   llama.cpp CLI success and unsuccessful flows.

## Rollback Plan
1. Rollback trigger: partial admission, incorrect commit/refusal ordering,
   unexpected nested writer or changed recovery/dispatch authority.
2. Rollback steps: stop admission and retain the failed candidate/evidence; repair
   the demonstrated predicate before restarting. Do not discard partial stores
   or return to independent admission commits as a repair.
3. Data/state recovery notes: process death after commit retains admission, not
   evidence that a physical tool ran. Separate stores and physical effects remain
   outside this transaction.

## Versioning Decision
- Version bump type: pending normal commit/release policy; no release performed.
- Effective version/date: 0.6.2 worktree candidate, 2026-09-14.
- Downstream impact: public signatures and stored schemas remain unchanged;
  callers receive a complete admission or the transaction's failure/refusal.
