# Validator timing in protocol receipts

## Summary
- Change title: Preserve unavailable and reported validator duration.
- Owner: Orket Core.
- Date: 2026-09-13.
- Affected contract: `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`, section 15.

## Delta
- Current behavior: the dispatcher and receipt builder coerce missing timing to
  zero, truncate fractions and can fail after tool execution on NaN/infinity.
- Proposed behavior: dispatcher writes `protocol_receipt.v2`. Nullable duration
  and `validator_timing` distinguish valid reported context input from unavailable
  input. A reported value is not an instrumented measurement. Invalid metadata
  cannot turn a successfully observed tool result into a timing conversion error.
- Why required now: BT-4 requires unavailable telemetry to remain unavailable;
  there is no validator-duration measurement producer in the current runtime.

## Migration Plan
1. Compatibility window: historical v1 receipts remain readable without rewriting
   their timing or digest. Generic writer defaults remain v1 for older callers;
   the changed dispatcher explicitly supplies v2. No new executable alias is added.
2. Consumers must accept nullable/fractional durations in v2 and honor provenance.
   V1 numbers cannot be retroactively certified as measured. Existing run-level
   materialization creates a separate event-linked digest and retains source
   timing; it does not rewrite source receipts.
3. Validation gates: real file reads through ToolBox/ToolDispatcher, typed negative
   contracts, on-disk receipt/digest retention, append idempotency, v1/v2 artifact
   replay and materialization, and matched installed-package checks. Exact results
   and limits are recorded in the canonical architectural-truth plan.

## Rollback Plan
1. Trigger: a required consumer cannot preserve the v2 nullable/provenance fields.
2. Stop new dispatcher execution while correcting that consumer. Do not resume the
   fabricated-zero producer as a successful rollback or relabel v2 as v1.
3. Preserve all source receipts and their hashes; no data migration is required.

## Versioning Decision
- Wire version: `protocol_receipt.v2` for the changed dispatcher producer.
- Effective date: 2026-09-13 worktree implementation; no release or tag is claimed.
- Downstream impact: receipt consumers must distinguish reported and unavailable
  timing. This change neither measures validation nor changes governed-agent SDK
  latency, connector monotonic timing, authorization or tool-result authority.
