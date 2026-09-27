# Sandbox event publication ownership

Status: Active contract
Last updated: 2026-09-27

## Admission and ownership

`SandboxLifecycleEventService.emit()` captures detached event values reserved for
primary and fallback publication before its first await. It selects the repository port,
spool, dead-letter and legacy-lock paths, and replay retry limit at invocation
entry. Relative paths bind to that invocation's working directory. Later caller
mutation, directory changes or failed repository mutation cannot replace the
captured fallback bytes. Repository implementations remain trusted ports; this is
not an atomic snapshot of their external state or filesystem contents.

The publisher captures metadata and payload before generating the event identity.
Direct service admission accepts an exact `SandboxLifecycleEventRecord` and
captures its declared fields without invoking caller copy, dump or serializer
hooks. Both reuse `capture_log_event_inputs` from
`orket/core/contracts/log_event_inputs.py`. Supported values are exact built-in
strings, booleans, integers, finite floats and `None`, nested in exact dictionaries
with exact string keys, lists or tuples. Tuples retain their JSON array encoding.
Custom objects and subclasses, cycles, non-string keys, non-finite floats and
excessive recursion refuse with `E_LOG_EVENT_INPUT_UNSUPPORTED` before repository
or spool effects. Unsupported input is an admission failure, not fallback intent.
Callers must explicitly normalize custom values before publication. No arbitrary
Python hooks are invoked to discover a representation. Existing JSON event fields
and the event-ID formula for admitted values stay unchanged.

Repository and logger ports remain selected borrowed resources, never deep-copied.
The capture is a synchronous snapshot of supported values before the first wait;
it does not provide atomicity against concurrently mutating native threads or a
bounded CPU/memory budget for arbitrarily large built-in graphs. Replay validates
decoded records against the same value boundary before passing a detached record
to the repository. Invalid retained values remain explicit failures with the spool
available for inspection; they do not consume a repository retry.

One existing `run_owned_io` admission retains emit or replay through repository
completion, file effects, handle closure and native lock release. Repeated caller
cancellation and elapsed caller timeouts wait for that admission to settle. A
native or publication failure takes precedence over cancellation. Primary refusal
still selects fallback; if both sinks fail, `SandboxLifecycleError` retains the
primary diagnostic and the spool failure as its cause. Interruption can therefore
leave a committed primary event, spool row, retry update or dead-letter row.
There is no forced-stop deadline for an unresponsive trusted repository or native
worker. Inspect retained state before retrying after failure or interruption.

The required replay-failure warning runs in the existing owned worker with its
event identity, retry values, selected spool path and exception information
captured explicitly. Its configured standard handlers settle before the admission
returns; handler failure remains outward failure and can leave earlier SQLite
publications with the original spool intact. This covers that diagnostic call,
not all logging preparation, handler configuration or optional logging policy.

## Cooperating spool callers

Fallback append and the complete read/replay/commit cycle share the existing
host-native nonblocking `NativeFileLocks` mechanism for the selected spool path
and `events` key. Native identity files remain under `<spool-name>.owners/` after
release or process exit. Preserve them while processes may use the spool.

When replay finds a spool, an active cooperating owner makes it return zero counts
with `lock_acquired=false`. A missing spool retains the existing zero-count no-op,
after checking the legacy sentinel. The false flag identifies contention; a
zero-count result alone is not proof of native lock acquisition.
A fallback append that encounters an active owner fails
explicitly with `E_SANDBOX_EVENT_SPOOL_UNCERTAIN:owner_busy` inside the combined
sink error. It cannot report `fallback` without completing publication. Callers
may separately retry a refused event after resolving contention; replay does not
enqueue the refusal. This nonblocking policy also prevents a recursive producer
inside a repository callback from waiting on its enclosing replay owner.

Native ownership is host-local and applies to cooperating callers. It does not
provide distributed locking, containment against path replacement, durability
against power loss, or protection from arbitrary external file writers.

## Retained history and migration

Existing event and spool JSON schemas remain unchanged. Replay accepts legacy
plain event rows and current `{record, retry_count}` rows. A failed repository
append receives a detached copy; its mutation cannot replace the owned decoded
event used for retry or dead-letter publication. Failure increments the selected
retry count; reaching the selected limit appends
to the existing dead-letter file. Requeued rows publish through the existing
same-directory temporary file and replacement. Malformed rows and read failures
remain explicit and leave retained spool evidence available for inspection.

SQLite events, dead-letter append and spool replacement/removal are separate
effects. A later failure preserves earlier effects. A failed spool commit can
leave both its original rows and already appended dead-letter evidence; a later
replay can duplicate that evidence. SQLite's existing event-ID replacement
behavior is unchanged. This contract makes no exactly-once or rollback claim,
and adds no scheduler or automatic invocation of replay.

Any existing legacy `<spool-name>.lock` entry causes
`E_SANDBOX_EVENT_SPOOL_LEGACY_OWNER_UNCERTAIN` before spool admission, even if the
spool itself is absent. It is never silently removed or inferred stale. Stop old
writers/replayers, inspect their state and retained spool evidence, and resolve
the legacy sentinel through separately authorized maintenance before upgrading.
Concurrent old/new deployments on one spool are unsupported. Do not roll back to
the old lock protocol while new callers may still be active.

## Verification boundary

Required integration controls use actual files, SQLite and child processes with
declared native/repository scheduling barriers. They cover input capture, busy
refusal, recursive emission, process-exit recovery, native acquisition and release,
read/write/close/replacement/removal, repeated cancellation, caller timeout and
partial failure. A 0.5-second independent SQLite response bound tests event-loop
responsiveness under controlled latency. Installed/native platform acceptance and
real Docker/provider acceptance remain separate observations in the active plan.
Process controls bind the child's interpreter and selected package/service origin
to the parent independently of the test harness location. Harness containment is
not evidence of correct installed-package imports.
