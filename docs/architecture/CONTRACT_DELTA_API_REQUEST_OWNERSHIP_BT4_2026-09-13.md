# Contract Delta: API request lifetime ownership

## Summary
- Change title: Retain active ASGI request ownership during application shutdown.
- Owner: Architectural-truth BT-4.
- Date: 2026-09-13.
- Affected contract(s): `docs/specs/API_RUNTIME_LIFECYCLE.md`, API transport availability.

## Delta
- Current behavior: The container could report successful close while an active
  authenticated approval request's native command and descendants kept running.
  Only explicitly registered background tasks and resources were collected.
- Proposed behavior: The container admits and owns each HTTP/WebSocket ASGI
  invocation, including response streaming and awaited connector work. Close stops
  admission, cancels active invocations once and awaits their cleanup before
  resources and engine. Request and close waiters observe the same retained typed
  cleanup outcome, including unconfirmed command termination. Caller cancellation
  cannot detach the invocation; request descendants cannot await their own close.
  New HTTP requests receive 503 after admission stops, including health. New
  WebSockets receive a pre-accept close; established sockets close with code 1001.
  An interrupted HTTP response that already started is truncated, never rewritten
  as a successful complete response. ASGI lifespan itself is not a request owner.
- Why this break is required now: A real TCP approval/command counterexample
  demonstrates that the previous successful-close claim omitted active work.

## Migration Plan
1. Compatibility window: No shim or alternate application factory. Existing
   request payloads, authorization and normal version headers remain unchanged.
2. Migration steps: Compose pure ASGI ownership in the existing app factory;
   release event sockets in `finally` and capture interaction cleanup dependencies
   before closing starts. Callers must tolerate unavailable or truncated responses
   during shutdown and inspect durable run/effect state before retrying effects.
3. Validation gates: Real authenticated TCP approval cancellation with native
   descendants; streaming TCP; real ASGI WebSocket routes; retained-failure and
   repeated-cancellation contracts; existing API/authorization regressions and
   isolated Windows/Linux Python 3.11/3.12 package acceptance. Exact results and
   scope are recorded in the architectural-truth plan.

## Rollback Plan
1. Rollback trigger: A demonstrated normal-request or shutdown regression.
2. Rollback steps: Revert this bounded container/transport/cleanup change and its
   authority updates together; restore the explicit unowned-request limitation.
3. Data/state recovery notes: No durable schema change. Close never grants retry
   authority or resolves uncertain remote effects. Preserve existing journals.

## Versioning Decision
- Version bump type: Patch when this worktree is released under the core policy.
- Effective version/date: Candidate changes dated 2026-09-13; no release made.
- Downstream impact: Shutdown transport availability changes as described above.
  Unregistered detached tasks, arbitrary blocking threads/resources, remote
  termination, host death and general shutdown deadlines remain outside this
  bounded local ASGI ownership guarantee.
