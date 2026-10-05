# Model-stream invocation lifetime

Status: Active
Last updated: 2026-10-04
Owner: Orket Core

Provider error events retain their exception class, including errors with an empty
message. No timeout budget changes accompany this diagnostic correction. Scope:
`docs/architecture/CONTRACT_DELTA_WORKFLOW_WINS_2026-10-04.md`.

The builtin `run_model_stream_v1` owns its admitted provider iteration and cancel
watcher through settlement, using `SHARED_IO_CANCELLATION.md`. Captured request,
provider selection and target refusal retain their existing contracts. This does
not admit another provider or change event/commit schemas.

The invocation closes its returned iterator when it exposes a close port, after
normal exhaustion, STOPPED/ERROR, event-publication failure, timeout or caller
interruption. It explicitly closes before requesting a decision/finalization
commit. A close failure refuses completion; it propagates with the interrupted
body retained in normal exception context. Resource-free iterators without close
ports remain supported; arbitrary iterators cannot acquire an unproved resource
cleanup guarantee from this interface.

Caller interruption reaches the owned operation once. Later cancellation cannot
abandon its iterator or cancel-watcher cleanup. The existing turn timeout requests
interruption and waits for cleanup; it is not a forced resource-stop deadline.
Successful cleanup after caller cancellation still returns cancellation, whereas
an actual cleanup failure remains visible. No subsequent commit is requested on
those paths. Internal provider ERROR and timeout retain the existing fail-closed
decision intent after successful cleanup.

The builtin owns iterators returned for its invocation. This grants no authority
to close a borrowed provider or unrelated client.

Application composition supplies real stream adapters with an explicit
`http_client_owner` implementing `ModelStreamHttpPort`. Raw OpenAI-compatible and
Ollama constructors require that port; callers previously relying on implicit
native construction must provide `ModelStreamHttpService`. The abstract
`start_turn`/`cancel` interface and Stub construction are unchanged. The builtin
composes the port using its captured environment and directory after target
admission, without rereading ambient proxy, trust, key-log or Ollama credentials.
Stream/non-stream selection binds with the same inputs. Provider configuration
and port routing must agree; supplied ports are trusted capabilities.

The HTTP service acquires separate resources for each turn, retains native client
construction in the shared worker owner, and registers partial transports. The
same turn owns responses, line/SDK iterators, client and transports. Teardown
attempts every resource in reverse acquisition order using the existing HTTP
resource owner. A retained construction failure escapes after cleanup. Explicit
cleanup failure escapes with all failures retained; neither requests a successful
completion. Provider HTTP/body errors keep ERROR-to-fail-closed decision semantics.

Non-streaming and zero-token fallback requests use the same owned asynchronous
client. There is no detached synchronous POST worker. Preserve local token limits,
synthetic empty-content tokens, request headers, OpenAI timeout budgets and disabled
redirects, and Ollama SDK redirects with separate connect/stream budgets. Later
caller interruption cannot abandon an admitted construction or cleanup operation.
Closing local connections does not prove termination of remote inference.

Source proof uses controlled real HTTP, including partial bodies, pending-response
EOF, acquired transport cleanup and API shutdown. Actual model inference, installed
behavior and hosted Quality acceptance remain separate queue gates.

Migration and proof scope:
`docs/architecture/CONTRACT_DELTA_MODEL_STREAM_ITERATOR_D_2026-10-01.md`.
