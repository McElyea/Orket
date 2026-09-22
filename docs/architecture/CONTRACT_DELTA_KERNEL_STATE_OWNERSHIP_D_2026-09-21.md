# Kernel state input, observation and commit ownership

## Summary
- Change title: Owned Kernel JSON and exact serialized commit authority
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-21
- Affected contracts: Kernel action-path input/output, commit authority and async publication
- Status: implemented; source/installed scoped acceptance recorded in the canonical plan
- Durable authority: `docs/specs/KERNEL_PUBLICATION_INPUTS.md`

## Delta
- Before: borrowed admission responses can change retained authorization; event
  and approval nested values can mutate retained history without recomputing its
  digest. Commit accepts an unrelated APPROVED record and permits overlapping
  same-key publication. Direct requests can change after hashing or validation.
- After: invocation JSON, state publication and returned observations have separate
  ownership. The caller may edit returned dictionaries without changing retained
  authority/history. JSON remains the existing public wire contract.
- One pure admission/approval identity rule serves credential issuance and commit.
  Commit observes accepted admission, matching session/proposal/decision approval,
  existing-event binding and same-key cache under one runtime lock through record,
  event and canonical-state publication. After successful publication, identical
  concurrent keys return the retained response without a second commit event.
- Existing public exports point to one commit implementation. Existing idempotency
  key, response vocabulary, reason ordering, caller-observed execution fields and
  packet1 approve/deny semantics remain. This introduces no execution verifier.
- Publication failures propagate where they did previously; effects may already
  exist. In-memory state/event operations are not a durable transaction, and direct
  global/private-map mutation is outside the trusted public-input boundary. A
  failure after event append but before cache publication can leave an event;
  retry can append another. Serialization is not crash/failure atomicity.
- Async engine mutation/approval paths retain owned native workers and required
  SQLite publication through repeated cancellation and timeout. API shutdown joins
  admitted publication. Failure remains observable after cancellation; a timeout
  can follow a completed effect. Interface observation calls also use owned workers.
- Application captures immutable operator environment before worker admission,
  shares it with nested invocations and resets the scoped binding after settlement.
  Explicit empty environment stays authoritative. No HTTP payload selects this input.
  Credential consumption still samples default expiry time after acquiring its lock.

## Migration Plan
1. Treat all returned values as detached observations. Request/decision JSON is
   captured before relevant validation/hash/lock waits; unsupported JSON refuses.
2. Supply an approval for the exact admitted identity. REJECT, QUARANTINE and
   unknown admission decisions cannot commit or issue a credential.
3. Retain .75 credential/expiry acceptance and new ownership, authorization,
   concurrent-publication and effect-parity controls in source/installed proof.
   Capture original failures and healthy controls; do not change deadlines.
4. Correct stale planner/router mutable-context authority text using its existing
   frozen contract and bounded proof; do not infer whole decision-node purity.
5. Use engine async mutation/approval methods from async embeddings. Direct
   synchronous Kernel calls still require worker ownership; global Kernel clocks,
   lifetime and helper/sync-bridge owners remain separate work.

## Rollback Plan
1. Revert implementation, callers and authority together on changed accepted
   behavior, input ownership, idempotency or publication semantics.
2. Preserve failed evidence and inspect retained state after publication failure.
   Do not infer rollback, durable restart or connector execution from Kernel status.

## Versioning Decision
- Version bump type: patch remediation with stricter input/authorization contracts.
- Effective version/date: 0.6.76 / 2026-09-21.
- Downstream impact: mutable Python aliases no longer modify retained state;
  invalid/foreign authority refuses. Global state lifetime, other clock/environment
  inputs, general synchronous lock safety, E/CAP and lane acceptance remain open.
