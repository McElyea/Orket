# Guard Review Retry Requeue

## Summary
- Change title: Align system retry transitions with failed guard-turn scheduling.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contract: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`.

## Delta
- Opening behavior: a recoverable missing read at `awaiting_guard_review`
  schedules `ready`, but the transition policy rejects it, interrupting failure
  closeout before the intended requeue and retry-count save.
- Required behavior: extend the existing system retry exception from
  `in_progress` to `awaiting_guard_review`, only for `ready` with the existing
  `retry_scheduled` / `runtime_guard_retry_scheduled` reasons. Both gate hooks
  remain enforced. Ordinary status requests and unrelated reasons remain denied.
- Reason: an admitted retry must produce its stated lifecycle result without
  promoting failure to a successful guard decision. Existing card writes clear
  the old completion context/reference; dispatch closeout remains unsatisfied.

## Migration Plan
1. No schema or evidence migration; no historical failure is rewritten.
2. New system retry requests use the repaired transition. Ordinary model tools
   cannot opt into this action by supplying action/reason argument fields.
3. Gates: contract negatives and hooks; actual failed-read tools and SQLite
   requeue/blocked outcomes; stale acceptance rejection; live model failure and
   separately dispatched fresh acceptance. Full source/installed gates remain
   required for whole BT-3 acceptance.

## Rollback Plan
1. Trigger: broadened model authority, successful terminal reopening, lost failure
   truth, bypassed gates or reuse of a stale completion request.
2. Repair the scoped exception while retaining failed requests and their evidence.
   Do not force persistence around a rejected transition.
3. No production state was migrated. A requeue does not promise effect rollback,
   automatic resume or atomic publication across card/control-plane stores.

## Versioning Decision
- Effective date: 2026-09-12. No commit, release or version bump in this checkpoint.
- Definition, receipt and event schemas remain unchanged; only the admitted
  system retry source-state set changes.
