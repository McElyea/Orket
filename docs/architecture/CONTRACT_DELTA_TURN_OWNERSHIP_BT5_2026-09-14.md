# Governed turn ownership and dispatch uncertainty

## Summary
- Change title: Exclude concurrent turn callers and retain unresolved dispatch.
- Owner: Orket Core.
- Date: 2026-09-14.
- Affected contracts: `CONTROL_PLANE_TERMINAL_AUTHORITY.md`, governed start-path
  matrix, `docs/ARCHITECTURE.md`, `CURRENT_AUTHORITY.md`.

## Delta
- Current behavior: separate callers can enter the same executing turn. A tool
  cancellation after a physical effect can look like an untouched checkpoint;
  a raised exception can publish pre-effect failure. Step and journal writes
  are separate.
- Proposed behavior: canonical governed turn invocation holds the shared native
  lock mechanism; dispatch admission precedes toolbox entry; observed step/effect
  publication is atomic. Unresolved admission blocks reentry, recovery and
  preflight/terminal release. Existing epic continuation identity is preserved.
- Why this break is required now: retained real composed dispatch controls
  contradict BT-5.3/5 ownership and effect truth, including post-write interruption.

## Migration Plan
1. Compatibility window: stop older writers before using the candidate. There is
   no mixed-version dispatch guarantee or compatibility bypass.
2. Migration steps: preserve current stores and native ownership files. New
   dispatches use the existing StepRecord schema with `dispatch_started` values.
   Historical unmarked unfinished attempts require separately admitted evidence;
   their migration remains open, and no old outcome is rewritten here.
3. Validation gates: real source and installed Windows/Linux Python 3.11/3.12
   conformance, native caller death, cancellation/transaction rollback, continued
   epic lock behavior, and actual installed llama.cpp CLI success/failure.

## Rollback Plan
1. Rollback trigger: dispatch admitted without durable marker, wrong-input
   observation, duplicate effects, partial publication or lost ownership.
2. Rollback steps: stop admission, retain the failed candidate and all evidence,
   repair the predicate and rerun its acceptance. Do not return to permissive
   reexecution of marked uncertain operations.
3. Data/state recovery notes: lock release alone is insufficient. A surviving
   local/remote effect needs explicit observation before reconciliation. No new
   operator recovery endpoint or historical repair is claimed.

## Versioning Decision
- Version bump type: pending normal release/commit policy; no release performed.
- Effective version/date: 0.6.2 worktree candidate, 2026-09-14.
- Downstream impact: busy and uncertain turns refuse reuse; consumers must retain
  unknown status and the control-plane/native ownership files. No wire schema bump.
