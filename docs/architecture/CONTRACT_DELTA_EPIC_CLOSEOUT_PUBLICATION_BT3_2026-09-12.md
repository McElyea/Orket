# Epic Closeout Publication

## Summary
- Change title: Atomic control-plane closeout and ordered epic success publication.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md` and
  `docs/architecture/event_taxonomy.md`.

## Delta
- Opening behavior: a final control-plane or run-ledger write abort leaves the
  session done and a success row already published. Control-plane closeout itself
  separately commits attempt, step/effect, final truth and final run state.
- Required behavior: control-plane closeout borrows explicit transaction-scoped
  repositories and commits those records together. Exceptions/cancellation before
  commit roll back the closeout. Serialized repeated calls reuse matching retained
  closeout evidence after checking journal integrity; conflicting terminal
  requests, missing evidence and damaged history fail without rewriting it.
- Session done and the success ledger are published only after control-plane and
  run-ledger finalization succeeds. Earlier failure cannot emit those completion
  claims. This does not make all runtime stores or support exports one transaction.
- Publication errors propagate without reclassifying accepted work as failed or
  masking the original failure with an illegal terminal-state transition.

## Migration Plan
1. Keep existing database locations and schemas. Add an explicit transaction port
   for related control-plane repositories; standalone repository calls retain
   their existing commit semantics.
2. Preserve retained historical evidence. Missing/conflicting closeout evidence
   is not silently recaptured by idempotent reentry.
3. Prove actual SQLite aborts, repeated/conflicting closeout, cancellation and
   independent-process interruption. Wider publication recovery remains required.

## Rollback Plan
1. Trigger: partial closeout survives rollback, conflicting closeouts both win or
   a valid retained closeout cannot be inspected/reused.
2. Repair the transaction and evidence checks. Do not restore early session or
   success claims or reseal historical records.

## Versioning Decision
- Effective date: 2026-09-12; no schema migration, release or version bump here.
- Final truth still describes the accepted workload outcome. Downstream publication
  failure/restart recovery is separate from an atomic control-plane closeout.
