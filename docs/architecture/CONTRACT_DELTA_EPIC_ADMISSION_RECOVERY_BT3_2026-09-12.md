# Recovery Before Epic Initialization

## Summary
- Change title: Explicitly replace an uninitialized epic admission owner.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: card completion/admission; canonical Python `run_card`.

## Delta
- Before: an interrupted admission remains reserved with no takeover operation or
  marker distinguishing initialization from an unconsumed claim.
- After: `epic_run_admission.v2` records an atomic initialization marker, owner
  generation and retained recovery history. The Python epic entry accepts a bound
  `epic_admission_recovery_request.v1`. Transfer is allowed only before that marker;
  stale owners cannot initialize after replacement.
- Recovery records reuse `OperatorActionRecord`. No failed execution attempt is
  invented for a boundary before control-plane initialization.
- Identical request retries do not create another owner or initialization. Changed,
  stale, superseded and post-initialization requests fail closed.

## Migration Plan
1. Admission v1 cannot establish this precondition and is rejected by the v2 reader.
2. Preserve old admission history and digests; do not backfill an uninitialized state.
3. Prove paused-owner fencing, native process death and replacement, duplicate/stale
   requests, history damage, initialization-marker refusal, and live llama.cpp flow.
4. Keep post-initialization owner recovery, remote operator surfaces and separately
   configured journal coordination open; no production migration occurs here.

## Rollback Plan
1. Stop recovery admission if a stale owner writes, a recovery repeats dispatch or
   a started invocation is mistaken for an uninitialized claim.
2. Retain original and replacement references and all effects while repairing the
   boundary. Do not clear the marker or reuse an old owner to restore execution.

## Versioning Decision
- New internal admission v2 and recovery request v1; effective 2026-09-12.
- Existing `run_card` calls retain their arguments. Recovery is an explicit new
  optional Python argument for epic targets; no release/CLI change is claimed.
