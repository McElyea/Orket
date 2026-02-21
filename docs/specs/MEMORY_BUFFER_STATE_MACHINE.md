# Memory Buffer State Machine

## Schema Version
`memory.buffer_state_machine.v1`

## Purpose
Define buffered-write lifecycle, commit idempotency, and recovery behavior.

## States
1. `buffer_open`
2. `commit_pending`
3. `commit_applied`
4. `commit_aborted`

## State Semantics
1. `buffer_open`: run is active and writes are buffered only.
2. `commit_pending`: commit requested after policy allows apply.
3. `commit_applied`: commit successfully applied atomically.
4. `commit_aborted`: commit rejected or failed irrecoverably with reason code.

## Required Abort Reason Codes
1. `policy_rejected`
2. `validation_failed`
3. `storage_apply_failed`
4. `payload_mismatch`

## Commit Identity and Payload
1. `commit_id = hash(run_id + memory_snapshot_id + policy_set_id)`.
2. `commit_payload_fingerprint` is computed over canonical buffered write payload.
3. Re-applying same `commit_id`:
matching payload fingerprint -> idempotent no-op
different payload fingerprint -> hard error (`payload_mismatch`)

## Recovery Ownership Rule
1. A `commit_id` may be owned by exactly one recovery worker at a time.
2. Ownership must be lease-based with explicit timeout and renewal.
3. Expired leases become eligible for reassignment.

## Crash Semantics
1. Crash in `buffer_open`: discard buffer.
2. Crash in `commit_pending`: recovery must either apply commit atomically or mark `commit_aborted` with failure reason.
3. Partial commit application is forbidden.

## Open Clarifications (Phase 0 Closure Required)
1. Lease timeout defaults and renewal cadence.
2. Recovery worker reassignment policy after lease expiry.

## Evolution Rules
1. State or reason-code contract changes require version increment.
2. Additive optional diagnostics fields are allowed within `v1`.
