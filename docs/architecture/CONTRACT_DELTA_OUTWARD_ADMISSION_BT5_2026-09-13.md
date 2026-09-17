# Outward admission transaction

## Summary
- Change title: Commit initial outward admission and its event under one owner.
- Owner: Orket Core, architectural-truth BT-5.
- Date: 2026-09-13.
- Affected contract: `docs/specs/OUTWARD_RUN_ADMISSION.md`.

## Delta
- Previous behavior: namespace checks race before the run insert; run and initial
  event commit separately. An event failure can leave a retained run without its
  admission event, and concurrent applications can admit two namespace owners.
- New behavior: the existing outward unit of work serializes the check and commits
  run, event and ledger head together. Missing historical admission events refuse
  reentry instead of being reconstructed from current state.
- Why required: shared workload authority cannot attach to a racy, partially
  published admission. BT-5 requires common CAS and one explicit authority chain.

## Migration Plan
1. No schema or execution-generation change; preserve existing valid history.
2. Preserve incomplete old admissions for inspection; no silent event backfill.
3. Verify event/ledger failures, concurrent owners, same-ID retry and process death.

## Rollback Plan
1. Stop submission if the atomic boundary regresses; preserve run/event evidence.
2. Do not resume an older writer to bypass a missing-event or namespace refusal.
3. No reverse history migration or deletion is authorized.

## Versioning Decision
- Patch candidate; contributor commit/tag policy applies when committing.
- No release, commit or push is performed by this slice.
- Shared catalog/final-truth convergence remains active BT-5 implementation work.
