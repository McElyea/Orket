# Governed native invocation lifetime

## Summary
- Owner: Orket Core.
- Date: 2026-09-17.
- Status: scoped source, four-cell installed and live llama.cpp proof pass; full-plan gates open.
- Affected contracts: governed child admission, cancellation, duplicate invocation
  refusal, process cleanup observations and event-loop ownership.

## Delta
- Application registers an invocation owner before awaiting native launch. Admission
  has no await between duplicate lookup and insertion on the owning event loop.
  A duplicate request creates no second child and cannot report the existing
  invocation's child as confirmed stopped.
- Launch retains its asynchronous operation until its process handle is captured.
  Caller cancellation then settles native teardown and diagnostic capture before
  propagating. Repeated cancellation cannot detach the cleanup operation.
- The shared owned-I/O helper has an opt-in `cancel_on_interrupt` mode: deliver
  one cancellation to an asynchronous resource owner, then join its cleanup.
  Existing thread/file users retain the default drain-without-cancelling behavior.
- Operator cancellation sees an admitted owner even while launch is pending.
  If launch cannot settle within the operator's grace period, the stop observation
  is false. The pending owner remembers cancellation and closes a subsequently
  launched child before bootstrap. Absence of a captured handle is not proof of
  absence of a native child.
- Cancellation payloads are captured before awaiting. The child receives the
  submitted reason even if its caller later mutates the source dictionary.
- Cleanup failures propagate as failures and leave the owner visible. They do
  not become clean cancellation, successful invocation or confirmed teardown.
- Each invoker is bound to one event loop at first invocation/control use. Later
  foreign-loop calls refuse with the registered
  `E_AGENT_INVOCATION_OWNER:event_loop_mismatch` error before changing ownership.
- Child framing, request/lease deadlines, capability receipts and SDK schema
  versions are unchanged. Diagnostic capture and termination remain actual native
  operations. Application ownership resides in
  `orket/application/services/governed_agent_process_owner.py`.

## Migration
1. Keep an invoker within its application event loop; construct another invoker
   for a separate application loop. Cross-loop reuse is unsupported.
2. Await cancellation settlement before disposing of its runtime owners. A pending
   launch, repeated cancellation or cleanup failure cannot authorize early teardown
   claims. An operation that never settles can delay caller cancellation.
3. Treat a duplicate refusal's `child_confirmed_stopped=False` as uncertainty about
   the existing invocation's lifetime, not permission to start another process.
4. Keep unresolved process owners and durable control-plane state available for
   inspection after cleanup errors. No generic automatic retry of an uncertain
   dispatched workload is introduced.

## Proof and limits
- Retained real-child counterexamples under `.tmp/d-agent-lifetime/` cover the old
  registration gap, interrupted launch, repeated teardown cancellation, false
  pending-launch stop acknowledgement, duplicate stop claims and mutable reasons.
  The private registration lock is removed; public pending-launch/operator tests
  exercise the replacement admission behavior.
- Current targeted tests include independent concurrent children, foreign-loop
  refusal and an injected teardown failure against a real live child. The canonical
  remediation plan owns the exact candidate verification disposition.
- This is cooperating application ownership. It does not establish hostile child
  containment, arbitrary descendant fencing, abrupt interpreter-death recovery,
  prompt cleanup of permanently stuck native calls or whole D3/D4 acceptance.
- The preceding 0.6.5 Linux approval/resume deadline failures remain unexplained.
  These independently demonstrated lifetime repairs are not a causal explanation
  or a declaration that those failures are closed.

## Versioning
- Candidate core patch `0.6.6`; SDK stays `0.7.0a1`.
- Cancellation settlement, duplicate-stop observations and cross-loop refusal
  change host behavior. Work-hours commits/tags remain local; the whole lane and
  retained deadline investigation and release/full-plan acceptance gates remain open.
