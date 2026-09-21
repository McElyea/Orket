# Driver construction, console input and transport lifetime

Status: Active contract delta
Last updated: 2026-09-21
Owner: Orket Core

Async driver embeddings use `await OrketDriver.create(...)`; synchronous
construction remains a pre-loop/worker API and refuses a running event loop
before configuration or provider effects. Async creation captures invocation
root, explicit environment and runtime settings before the owned constructor.
Relative project roots bind to that invocation root. Explicit empty environment
input is retained. Injected provider/filesystem/reforger ports retain identity;
this does not freeze their internal mutable state or snapshot authored files.

The shared runtime factory owns admitted construction and closes a returned
driver when interruption prevents transfer to its caller. Construction failures
remain visible under the existing unreturned-resource limit. A successfully
returned driver owns provider cleanup, including an explicitly supplied provider;
callers must close it before dropping that ownership. `close()` retains provider
close through repeated cancellation and exposes cleanup failure. It delegates
transport idempotency to the existing provider close contract.

API chat creation and interactive CLI mode use the same runtime owner primitives.
The CLI uses its post-startup captured construction inputs. Provider close gates
normal EOF/quit, request failure and interrupted exits. Cleanup failure cannot
produce a success exit. API chat retains its existing response and request-owner
lifetime semantics.

Console input runs in an owned worker. EOF is an ordinary input result, so EOF
while interruption is pending cannot replace cancellation with success. Native
input failure remains visible. An admitted blocking read must settle through a
line, EOF or input failure before the caller can finish cleanup; there is no
forced thread termination or new terminal-read deadline. Standard input remains
borrowed from the process and is not closed by the driver.

Model parsing and fallback prompt behavior move to the existing conversation
owner without a forwarding implementation. Broader mutable driver state,
remaining synchronous ConfigLoader callers and full D/E/CAP acceptance remain open.
Sandbox log ownership follows `CONTRACT_DELTA_API_SANDBOX_LOGS_D_2026-09-21.md`. API run observations now follow
`CONTRACT_DELTA_API_RUN_OBSERVATION_D_2026-09-21.md`. Proof records distinguish controlled local
HTTP/console effects from fresh model inference.
