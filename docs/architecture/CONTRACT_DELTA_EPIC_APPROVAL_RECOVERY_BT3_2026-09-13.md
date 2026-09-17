# Recovery of an interrupted epic approval continuation

## Summary
- Change title: Admit explicit recovery of a consumed approval pause under exclusive local execution ownership.
- Owner: Orket Core, architectural-truth BT-3.
- Date: 2026-09-13.
- Affected contract(s): `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`,
  `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`, `CURRENT_AUTHORITY.md`.

## Delta
- Previous behavior: a consumed approval pause remains uncertain after native
  process death, even when no child step/effect or output exists. A fresh standard
  caller cannot continue it. The opening native counterexample is retained at
  `.tmp/bt3-approval-recovery-before/report.json` (primary path, unmet recovery
  requirement, fixture provider). This refusal prevents unsupported redispatch.
- Implemented behavior: acquire an exclusive local execution lock before consuming
  or explicitly recovering a pause. New claims bind the stable lock-file identity.
  Hold ownership through restored execution and durable outcome/new-pause retention,
  then release before that caller enters export/preparation/publication. Other
  callers can independently finalize an already retained outcome. An explicit bound recovery
  request may consume one recovery grant after the previous owner relinquishes
  the lock; an active holder prevents takeover. Original checkpoint/authorization
  checks still govern continuation. Record requests and operator actions without
  rewriting the original pause, admission, child identity or accepted evidence.
  Approved recovery requires every referenced child to remain pre-effect;
  completed children do not acquire this grant. Verification status and exact
  evidence are retained in the canonical architectural-truth plan.
- Why this break is required now: claimed-pause interruption is a remaining
  required recovery gate. Empty card/effect observations alone cannot exclude a
  suspended old caller, and holding ownership through later export would obstruct
  the separately admitted export-owner recovery path.

## Migration Plan
1. Compatibility window: previously unmarked claimed pauses cannot acquire inferred
   ownership. Waiting pauses can receive the marker only with their new guarded
   claim. Existing retained outcomes/publications keep their recovery semantics.
2. Migration steps: add the ownership adapter and core reference, bind claims to
   it, retain per-pause recovery history in the existing publication journal, and
   expose one mutually exclusive `approval_recovery` input on canonical Python
   `run_card`. Preserve old bytes/digests; do not reset claimed state to waiting.
3. Validation gates: actual Windows/Linux locks across independent native processes;
   killed and paused holders; cancellation during acquisition/cleanup; stable file
   identity and replacement refusal; real-journal competing/idempotent/conflicting
   recovery; original checkpoint and post-effect/orphan-artifact refusal; denial;
   outcome-before-unlock; export after unlock; installed 3.11/3.12 acceptance and
   fresh live llama.cpp approval/recovery without repeated accepted work.

## Rollback Plan
1. Rollback trigger: concurrent local dispatch, changed original evidence, or
   continuation beyond checkpoint authority.
2. Rollback steps: disable new explicit recovery admission while preserving lock
   files, markers and recovery records. Keep uncertain runs unresolved.
3. Data/state recovery notes: a binary without the new ownership reader cannot
   safely recover marked consumed pauses. Preserve the journal and lock identity;
   replacement files or current workspace state cannot substitute for them.

## Versioning Decision
- Version bump type: patch with the eventual versioned release commit.
- Effective version/date: implemented candidate, 2026-09-13; final verification
  and remaining scope are recorded in the architectural-truth plan. Unreleased.
- Downstream impact: trusted local Python recovery input and retained local
  ownership/history. No CLI or authenticated remote takeover endpoint, lock expiry,
  remote-effect termination, arbitrary writer containment, independent-journal
  coordination or general unknown-workload recovery is inferred.

Implementation references: [Python Windows file locking](https://docs.python.org/3/library/msvcrt.html#msvcrt.locking)
and [Python POSIX file locking](https://docs.python.org/3/library/fcntl.html#fcntl.flock).
These API contracts do not replace native platform verification.
