# Issue-dispatch terminal publication transaction

## Summary
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contract: `CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

## Delta
- Retained Linux approval proof published a completed issue run and successful
  final truth before rejecting lease release for reversed time. Its lease remained
  active. The parent API correctly returned an unresolved outcome.
- Issue closeout now borrows execution and record ports from the existing SQLite
  transaction owner. Terminal, step/effect, recovery and resource publications
  commit together or roll back together. Concurrent callers reread under the lock.
- Reentry validates retained terminal and resource joins instead of silently
  returning for a run whose final-truth reference is present.

## Migration and versioning
1. Composition supplies a required transaction factory to the application service.
   No new schema, receipt version, public endpoint or compatibility alias is added.
2. Existing complete histories remain readable. Partial historical closeout refuses
   normal reentry without rewriting, backfilling or dispatching effects.
3. The original failed database and audit remain immutable. Reversed time remains
   invalid; this change neither clamps it nor attributes its host-clock cause.
4. Dispatch admission, physical effects and broader recovery remain separate
   authority obligations. This is an unreleased candidate pending installed proof.

## Validation and rollback
1. Retain controlled pre-repair failures after lease/resource writes, cancellation
   and reversed input, then verify rollback, retry, contention and history refusal.
2. Verify the built package through the actual installed card/approval boundary.
   Stop acceptance on any inconsistent retained join; preserve failed observations.
3. Do not restore split terminal publication as a success fallback.
