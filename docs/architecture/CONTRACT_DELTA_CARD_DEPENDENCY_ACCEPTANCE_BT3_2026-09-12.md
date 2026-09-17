# Card Dependency Acceptance and Dispatch

## Summary
- Change title: Use retained acceptance and consistent build scope for dependencies.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md` and
  `docs/architecture/event_taxonomy.md`.

## Delta
- Opening behavior: adapter readiness selection accepts any `done` row but
  withholds accepted `guard_approved` rows. Turn context treats archived and
  foreign-build prerequisites as resolved. Targeted/review strategy paths can
  avoid the readiness filter.
- Required behavior: application-owned build inspection and dependency context
  share the existing current receipt/evidence check. Only accepted prerequisites
  in the selected build resolve. Planner input contains admitted copies;
  selections cannot replace payloads, repeat identities or select unknown cards.
  Dependency inputs, target lifecycle and prerequisite acceptance are inspected
  again before turn effects. Stalled diagnostics retain rejection reasons.
- Reason: workflow status and strategy selection cannot confer completion or
  dependency authority. The change preserves the distinction between retained
  evidence and permanently current workspace state.

## Migration Plan
1. Remove the internal adapter `get_independent_ready_issues` method. Runtime
   callers use `card_dependency_service.read_card_dispatch_snapshot`; no duplicate
   selector or compatibility alias remains.
2. No database schema or historical evidence migration. Legacy receiptless rows
   keep their lifecycle but do not unlock dependent work. Foreign-build IDs do
   not gain new cross-build dispatch semantics.
3. Verify accepted/refused prerequisites, ordinary/targeted/review selection,
   planner payload isolation, changed dependency inputs and prerequisite reopening,
   final build receipts, and a real canonical provider-backed dependency chain.

## Rollback Plan
1. Trigger: rejection of correctly bound current-build prerequisites, loss of
   diagnostics, unauthorized strategy dispatch or stale dependency acceptance.
2. Repair the shared application inspection while retaining fail-closed receipt
   requirements. Do not restore a status-only success path.
3. No historical rows or artifacts are rewritten. Guards are not held across
   inference; later concurrent mutation and multi-store publication remain
   separate obligations.

## Versioning Decision
- Effective date: 2026-09-12; no commit, release or version bump in this checkpoint.
- Completion schemas remain unchanged. Dependency context and stalled events gain
  diagnostics. Internal adapter callers migrate to the application-owned selector.
