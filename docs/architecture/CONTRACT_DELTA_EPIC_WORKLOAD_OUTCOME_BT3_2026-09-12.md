# Retained Epic Workload Termination

## Summary
- Change title: Retain observed workload termination before completion inspection.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`, standard Python
  `run_epic`/`run_card` reentry and durable publication journal contents.

## Delta
- Opening behavior: inspection or initial preparation persistence can fail after
  workload termination but before retained preparation. Restart resets accepted
  cards and dispatches again. Cancellation before termination has the same risk.
- Required behavior: `epic_workload_outcome.v1` retains the original observed
  return/failure, request, policy, artifacts, transcript, effective configuration,
  observation time and export binding before asynchronous finalization work.
  Reentry resumes inspection/preparation from those inputs; acceptance still gates
  completion. Retained failure reason/class survive recovery and remain failures.
- A started invocation without any retained outcome/preparation/publication record
  refuses redispatch with `E_EPIC_WORKLOAD_OUTCOME_UNCERTAIN`. Card acceptance alone
  cannot establish whether a workload returned or failed. Automatic owner takeover
  at that boundary remains unimplemented; this is an explicit uncertainty result.

## Migration Plan
1. Add `epic_workload_outcomes` to the existing publication journal without changing
   prior preparation/publication rows or digests. Do not backfill historical outcomes.
2. Preserve the journal and its committed WAL content with the original runtime,
   control-plane and acceptance evidence. Existing sufficient prepared publications
   retain their recovery path. Older running invocations without termination
   evidence now refuse automatic reset/reexecution.
3. Validate real inspection/preparation failures, native process loss before and
   after outcome retention, concurrent fresh reentry, transcript/effective-snapshot
   preservation, failure identity and damaged/missing/conflicting history refusal.
   Live accepted-work recovery must add no model receipts.

## Rollback Plan
1. Trigger: recovery redispatches accepted work, substitutes a fresh snapshot or
   transcript, or converts retained failure/uncertainty into success.
2. Preserve outcomes and effects, reject affected reentry and repair the protocol.
   Do not erase records or restore reset-first behavior.
3. Uncertain workload owner recovery and external export reconciliation remain
   required; a new session is not a repair for an uncertain prior invocation.

## Versioning Decision
- Effective date: 2026-09-12; additive internal `epic_workload_outcome.v1` schema.
- No release/version bump or production migration is performed in this worktree.
- Same-session callers must handle explicit workload uncertainty. Normal return
  remains distinct from accepted completion; no global atomicity is introduced.
