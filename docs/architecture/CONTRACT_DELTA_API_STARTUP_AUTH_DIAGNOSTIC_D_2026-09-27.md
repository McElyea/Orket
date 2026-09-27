# API startup authentication diagnostic ownership (D)

Date: 2026-09-27
Status: Active

## Existing boundary and correction

`ApiRuntimePreparation.open` acquires and owns the application's runtime graph.
`api_runtime_lifespan` initializes that graph through the existing
`ApplicationRuntimeLifetime.run_request` admission. Previously its complete
`authentication.validate_startup(LOGGER)` call executed on the event-loop thread.
The insecure-key critical diagnostic and insecure-Gitea-TLS warning could therefore
block that loop through an ordinary synchronous logging handler.

Capture the bound validator and selected logger alongside the existing owner
captures before the lifespan's first await. After owned root validation, await
that complete call through the existing `run_owned_thread`; only then initialize
the engine and register the broadcaster and subscription. No second queue,
daemon, security policy, or logging owner is introduced.

## Preserved authority and failure semantics

`ApiAuthenticationService` still owns its captured immutable environment, insecure
bypass policy, required-secret validation and TLS warning ordering. Its ordinary
synchronous API remains synchronous. Direct embedders keep the same method and
logger arguments. Canonical API lifespan now invokes custom synchronous handlers
on an executor worker; handlers requiring event-loop-thread affinity need to use
their own explicit compatible delivery contract. A logger object is captured by
identity; this does not freeze subsequent changes to its handlers or configuration.

The worker inherits the invocation's context variables through `asyncio.to_thread`.
Successful worker completion after caller interruption propagates cancellation
without starting engine initialization. Native failure remains failure and takes
precedence over repeated caller cancellation. Production/staging bypass refusal
still follows the critical diagnostic and precedes engine initialization. Existing
API preparation and lifetime owners perform their existing cleanup; no successful
readiness or HTTP admission is published for refused or interrupted startup.

This retains an admitted worker until completion. It cannot stop a native handler,
roll back its external effects, or impose a shutdown deadline. A stuck handler can
keep cancellation and close pending. Errors in independent cleanup retain the
existing aggregate-failure semantics. Error diagnostics emitted by other owners
and ordinary post-startup producers remain outside this change.

## Required proof and limits

The new integration module enters the public API factory and actual lifespan,
holds a real logging handler, executes SQLite while that handler is held, and
checks HTTP readiness remains refused. It covers both diagnostic branches,
success, repeated caller cancellation, exact native failure identity, failure
after cancellation, production/staging refusal, and pre-await bound-input capture.
Existing startup controls retain real HTTP, WebSocket and close regression breadth.
Controlled native stalls establish local responsiveness and ownership; they do
not contact Gitea or establish remote effects, generic logging safety, installed
package parity, or another operating system's behavior.

Execution receipts and observed outcomes belong to the ignored draft review and
subsequent canonical plan record. This scope does not close optional logging CWD
capture/lazy-writer preparation, other required logging callsites, or the full D lane.
