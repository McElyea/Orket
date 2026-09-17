# Retained Epic Publication Recovery

## Summary
- Change title: Recover prepared epic publication before card reset or workload dispatch.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`, standard Python
  `run_epic`/`run_card` same-session semantics, durable store locations and event taxonomy.

## Delta
- Opening behavior: restart after an accepted workload's publication failure resets
  cards and creates a new invocation, dispatching work again.
- Required behavior: retain original prepared publication arguments, request binding
  and monotonic confirmed progress in `<runtime_db>.epic-publications.sqlite3`.
  Recover through the selected repositories before card mutation. Matching completed
  reentry verifies retained effects and returns its transcript; new work uses a new
  session. Conflicting requests, changed acceptance and damaged/lost history fail closed.
- Retained failed work still reports failure after its publication completes.
- The protocol starts after control-plane closeout, summary and current export
  preparation. Earlier interruption and ambiguous remote exports remain required
  BT-3 work. This is not a transaction across every store or exactly-once events.

## Migration Plan
1. No old run is silently assigned a new publication plan. Finalized invocations
   missing the plan are refused before card reset. Keep old evidence unchanged.
2. Preserve the new journal, including committed WAL pages, with runtime and
   control-plane databases and card acceptance evidence. Relocation remains gated.
3. Validate SQLite aborts, effects committed before process death, independent
   concurrent restart, readback confirmation, corruption/conflict refusal and
   accepted live workload recovery without new model receipts.

## Rollback Plan
1. Trigger: recovery redispatches work, loses accepted history, rewrites a confirmed
   effect or publishes success without readback proof.
2. Repair the publication protocol and reject affected reentry until evidence is
   sufficient. Preserve plans and effects; do not erase the journal or restore reset-first behavior.

## Versioning Decision
- Effective date: 2026-09-12; new internal `epic_publication.v1` retained schema.
- No release/version bump or production migration is performed in this worktree.
- Callers explicitly reusing a published session now recover it. Fresh execution
  requires a new session ID. Default callers that generate a new ID remain fresh executions.
