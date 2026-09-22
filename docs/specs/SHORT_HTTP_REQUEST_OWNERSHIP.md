# Short HTTP request ownership

Owner: Orket Core
Last updated: 2026-09-22
Status: Active scoped contract; implementation acceptance remains required

Artifact-export and builtin HTTP requests receive the application-owned
`HttpRequestPort`. Each request owns one native client construction, the loaded
response and all acquired client/transport cleanup. Application composition reuses
the captured network policy, native construction supervisor, runtime owner and
resource cleanup from `GITEA_HTTP_CLIENT_OWNERSHIP.md`; there is no second proxy
compiler or cancellation loop. A request cannot return success before cleanup.
Partial construction and interrupted construction retain and close acquired
resources. Repeated cancellation cannot abandon admitted native work or cleanup.
Cleanup failures remain observable; physical close does not prove remote rollback.

The exporter factory captures environment and lexical invocation root together
with its binding. Explicit empty mappings have no ambient or registry fallback.
Raw exporter embeddings supply the request port; native construction refuses
event-loop entry. Async embeddings run the factory through the existing owned
native worker. Export bindings, Basic authentication, allowed statuses, unavailable
error mapping, retained commit intent and recovery behavior stay authoritative.
HTTP timeout remains 30 seconds and redirects stay disabled.

Builtin HTTP retains its existing per-operation ambient configuration boundary.
The application request service captures environment and cwd before its first
await on each request; later requests can observe operator changes. Explicitly
configured request services snapshot their supplied mapping at construction.
Invocation arguments are copied before dispatch so reported effect identity matches
the sent body despite caller mutation. Nested JSON, query and header inputs are
copied before native dispatch. HTTP
allowlist and URL checks still occur before resource acquisition, and GET/POST
result, error and body semantics remain unchanged. The existing outer connector
deadline includes native construction and cleanup; no deadline is extended.
Non-finite client timeout inputs fail before acquiring resources.

Controlled native trust holds, actual TCP/TLS requests, independent SQLite work,
partial acquisition, repeated cancellation, timeout and failure controls establish
the scoped boundary. Disposable Gitea export/recovery proof and teardown are
separate acceptance obligations. This does not establish ordinary TLS latency,
termination of a stuck native thread, immutable trust-directory contents, exporter
Git/filesystem ownership, Linux clock repair, full coverage or E/CAP acceptance.
