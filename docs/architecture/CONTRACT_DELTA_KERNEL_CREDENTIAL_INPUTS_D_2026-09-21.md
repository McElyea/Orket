# Kernel credential observations and authorization binding

## Summary
- Change title: Explicit credential inputs and exact admitted approval identity
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-21
- Affected contracts: kernel credential issue/consume/invalidation, hash-only events
- Status: implemented boundary; scoped verification is recorded in the canonical plan
- Durable authority: `docs/specs/KERNEL_POLICY_INPUTS.md`

## Delta
- Before: ambient key/time/randomness and borrowed requests could change during
  validation; rejected admissions and foreign APPROVED rows could issue tokens.
  Eight opening cases and nine identical current control cases fail on published .74.
- After: application captures owned request and immutable trusted input; pure
  credential hashing/expiry/binding consumes explicit values. Secret fields are
  excluded from representations. Exact admission/approval identity is checked
  under the runtime lock through issuance. Rejections publish no credential.
- One aware UTC instant determines each credential operation's times. Issue time
  is captured on entry; default consumption observes time after lock acquisition
  so expiry reached during validation or contention still refuses use. The first
  candidate captured consume time too early; its two expiry counterexamples and
  the healthy published .74 control are retained before corrected acceptance.
  Environment rotation between invocations remains effective; no mid-call drift.
  Response shapes, entropy formats, HMAC, canonical digests, binding/replay/expiry
  reason precedence and existing session/proposal invalidation stay authoritative.
- Trusted input is never deserialized from request JSON. The existing development
  signing default is preserved without claiming a new production trust boundary.
  An issued token is not evidence of connector execution or durable recovery.
- Reusing a stored token hash or identity hash is refused before any mutation;
  explicit identities cannot overwrite a used credential and reset replay state.
- Record mutation still precedes event publication. A callback failure propagates
  and can leave a record without its event; no transactional record/ledger or
  durable recovery guarantee is introduced. A failed consume remains used and
  cannot be replayed. Inspect state after failure rather than assuming rollback.

## Migration Plan
1. Low-level credential effects supply typed inputs and explicit invalidation time;
   application wrappers capture defaults or accept a trusted typed input.
2. Existing direct public wrappers retain response shapes. Rejected admissions and
   approvals for a different session/proposal/decision now fail before issuance.
3. Prove original counterexamples and same-current-tests installed .74 controls;
   explicit time/identity determinism, strict expiry/replay, key/request rotation,
   credential secrecy, locked approval identity, source/installed callers and
   actual event/state effects. Controlled clocks are labeled as such.

## Rollback Plan
1. Inspect token/ledger state after failure; preserve counterexamples and failed
   proof. Do not relabel in-memory records as durable or executed effects.
2. Revert implementation, callers and contract together if stable binding,
   expiry/replay, retained BT gates or truthful event publication regress.
3. Shared global runtime maps, general ledger clocks and synchronous lock ownership
   are not closed by this scoped input change; preserve their remaining D work.

## Versioning Decision
- Version bump type: patch remediation checkpoint with explicit input migration.
- Effective version/date: 0.6.75 / 2026-09-21.
- Downstream impact: required low-level inputs, consistent timestamps and stricter
  rejected/foreign approval refusal; no new shim, workload or containment admission.
- Remaining: broader Kernel state, async reachability, sync bridge, full adapter
  enforcement, Linux clock acceptance, E/CAP and explicit whole-lane acceptance.
