# API observation ownership

Owner: Orket Core. Date: 2026-09-19. Effective core version: 0.6.26.

## Delta

API hardware requests previously awaited an unretained thread. Cancellation or
application shutdown could return while the hardware observation still ran.
`ApiSystemQueryService.hardware_metrics` now owns that worker until settlement.
The interface retains presentation normalization. Hardware payloads and sampling
semantics are unchanged; the existing hardware cache and subprocess behavior remain.

`ApiEventService` captures an application root and copies nested event inputs
before dispatching the logging adapter in an owned worker. This selects its
synchronous file-write path; HTTP, WebSocket and startup callers await settlement.
Cancellation can follow a completed write. Write failure propagates instead of
being hidden behind the adapter's asynchronous logging queue. An authentication
rejection whose telemetry cannot be written may therefore return a server error;
it cannot authorize access. Event names and schemas are unchanged. Existing query
and invocation events describe observations/attempts, not completed effects.

`ExtensionModelCatalog` captures the selected environment at service construction.
Provider defaults and endpoint selection use that snapshot; explicit request
providers remain supported. A failed admitted inventory retains its provider
identity in the application error and rooted event, even if ambient settings
change while awaiting the provider. Expected HTTP/OS/runtime/type failures produce
the existing degraded 503 envelope. Validation errors retain their existing HTTP
mapping; unexpected programming errors propagate. Failure to publish the failure
event also propagates. No fallback provider is selected.

## Migration

The HTTP success schemas and explicit provider query parameter are preserved.
Recreate the API application or direct extension runtime service to rotate catalog
environment settings. `ExtensionRuntimeService` accepts an explicit `environment`;
its default captures the process environment at construction. This changes catalog
selection only, not every generation/voice/provider setting in that service.

Router embeddings supply an application event-service getter in place of raw
logging callbacks. System-router embeddings obtain hardware observations from
their system-query service. A custom extension service reports expected catalog
unavailability with `ExtensionModelCatalogUnavailable`, which owns the structured
error detail. Direct imports of retired interface logging/hardware aliases are
unsupported; no compatibility forwarding shim was added.

## Verification and limits

Before-state runs retain three actual metrics worker escapes and a loopback HTTP
failure mislabeled after provider rotation. One initial catalog fixture lacked
authentication and is retained separately from the corrected counterexample.
The focused repaired cohort exercises real ASGI routes, hardware observations,
files, and loopback HTTP. Held workers require concurrent heartbeat responsiveness
within 0.5 seconds and settlement within 3 seconds after fixture release.
Cancellation, timeout, shutdown, nested payload capture, write failure and separate
application roots are covered. Source/package/native checkpoint results live in
the canonical architectural-truth plan.

Worker ownership provides no hard deadline for uninterruptible OS I/O or hardware
subprocesses. Logging is not a transactional/crash-durable event store. Its global
subscriber registry and remaining queue-based callers are unchanged; this does not
claim cross-application WebSocket event filtering or whole-runtime logging purity.
The pre-existing clear-logs response can still return `ok` after a skipped write.
Those concerns remain under active C/D/E authority. Loopback catalog fixtures prove
HTTP behavior, not live model inference or provider deployment readiness.

## Rollback

Rollback requires a versioned source change with the prior router dependencies and
catalog selection semantics restored together. Stop and drain affected applications
before replacement. Retain already written events; interruption does not authorize
deleting or replaying them. No persisted schema migration is introduced.

Version decision: patch checkpoint; breaking internal embedding/selection behavior.
Compatibility status: breaking. Affected audience: all. Migration: required.
