# API sandbox log ownership and failure truth

Status: active bounded D contract delta; lane acceptance remains open.

The sandbox log endpoint captures the selected pipeline factory, workspace and
validated invocation before its first await. Invocation capture uses the existing
API policy input authority; later mutation of the strategy's returned object
cannot change the admitted method or arguments. Invalid invocation structure is
refused before pipeline construction. Existing supported method selection,
optional service forwarding, HTTP 400 and configured unsupported-detail behavior
remain intact.

The shared `open_runtime_owner` constructs an ephemeral pipeline on an owned
worker and closes a returned pipeline if interruption prevents transfer. The API
binds its selected log callable and reads it through `read_runtime_sandbox_logs`.
An admitted read remains owned through repeated cancellation, elapsed request
deadlines and shutdown. Required pipeline close gates success and failure exits;
native read or close failure remains visible. A factory cannot recover resources
that its constructor allocates and discards before returning an owner; that
existing limit remains explicit. No forced thread termination is promised.

`SandboxOrchestrator.get_logs` remains synchronous for pre-loop or worker callers.
It now refuses an event-loop thread before lookup or native work with
`E_SANDBOX_LOGS_REQUIRES_WORKER`. Async embeddings must use the application-owned
inspection service (with their bound `get_logs` callable) and retain ownership of
any pipeline they construct. The canonical API caller uses the shared owner.
This is a required migration for direct async library callers; supported API
clients require no request-shape change.

Log commands retain their existing ten-second timeout and service allowlist.
A nonzero native exit raises a visible runtime failure, including sandbox identity
and exit code, rather than returning stdout as successful logs. The API exposes
that dependency failure as HTTP 500. It does not substitute cached or partial
logs as a successful result. Ordinary log success retains its response shape.
Closing an ephemeral query pipeline does not delete the observed sandbox.

This change does not establish untrusted Docker isolation, redesign sandbox
creation or teardown, or close the broader `CommandRunner.run_async`, ConfigLoader,
adapter classification, captured-input and async-inventory obligations. Remaining
C/D/E/CAP acceptance and the Linux clock gate retain their separate disposition.
Proof in the canonical remediation plan and `.tmp/d-api-sandbox-query/` distinguishes
controlled native-child tests from actual installed API/Docker verification and
requires immediate exact-project resource teardown for the latter.
