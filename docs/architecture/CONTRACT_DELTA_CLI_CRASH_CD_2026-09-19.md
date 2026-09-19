# Captured CLI crash publication

## Summary

Owner: Orket Core. Effective date: 2026-09-19. Version: 0.6.30.
Affected contracts: fatal runtime CLI outcomes and diagnostic file publication.
Status: active implementation; whole architectural-truth acceptance remains open.

## Delta

The old `orket.logging.log_crash` retained a process-global rotating handler.
Later calls could write to the first workspace despite selecting another one.
The CLI narrated a relative filename rather than its actual destination, and a
diagnostic write failure could escape the original fatal-error handler.

Application `CrashReportService` owns publication over an explicit absolute
workspace and an injected clock (UTC host clock at standard composition). It
captures the error type, traceback and timestamp before dispatch. Storage owns
append, rotation and readback inside a retained worker and declares side effects.
There is no process-global handler, background queue or open log handle afterward.
The adapter returns the actual absolute path only after matching readback.

The runtime CLI captures its invocation directory before bootstrap. Its startup
diagnostic destination remains `<invocation>/workspace/default/orket_crash.log`,
including failures before argument parsing. `--workspace` continues selecting the
execution workspace; it does not retarget this process-level startup diagnostic.
Bootstrap imports are inside the fatal boundary. A publication failure prints the
original traceback and the diagnostic error to stderr, does not claim a saved
file, and retains exit 1. Interrupts retain exit 130. Successful publication prints
the actual absolute log path. The old adapter export is retired without a shim.

Native locks serialize admitted append/rotation operations on one resolved log
path. A busy owner is an explicit refusal, not an unbounded wait or silent drop.
Preserve `<log>.owners/` lock identities alongside the log; deleting a live lock
does not grant ownership. The existing 5 MiB threshold and five numbered backups
remain the defaults. An individual record may exceed the threshold. Existing
non-regular log/backup paths are refused. File data is flushed and synced before
closed-file readback. Publication and rotation are not a multi-file transaction;
a failed attempt can leave a partial append or partial rotation, which must be
inspected before retry. No power-loss, hostile-editor, remote-filesystem fencing
or exactly-once retry guarantee is added.

Cancellation and timeout retain admitted workers through append/readback and
native lock release. A worker failure remains visible during interruption. This
does not impose a hard deadline on a hung filesystem operation. The fixed proof
bounds are 0.5 seconds for independent-loop responsiveness and 3 seconds to settle
after release of a controlled worker hold. Diagnostic timestamps are observations,
not control-plane lease timestamps or replay identities.

## Migration Plan

1. Compatibility window: none for `orket.logging.log_crash`.
2. Embeddings construct application `CrashReportService(absolute_workspace)` and
   await `publish(exception, traceback_text)`. Supply a clock for deterministic
   inputs. Consume the returned path only after publication completes.
3. Preserve existing logs and numbered backups. No migration or deletion is
   required. Direct consumers must handle explicit storage/ownership refusal.
4. Validation gates: real sequential and concurrent roots, append and rotation,
   actual public CLI refusal, readback failure, busy native owner, interrupted
   worker lifetime, explicit clock/root capture, and installed Windows/Linux
   Python 3.11/3.12 parity.

## Rollback Plan

Drain admitted workers before replacing the service and callers together. Retain
logs, backups and native ownership files. Inspect partial publication after
failure; do not blindly retry or restore global-handler routing and false saved
claims. A rollback requires a new version and the same public fatal-status proof.

## Versioning Decision

Patch checkpoint with a breaking embedding import change; migration required.
Runtime command spelling and ordinary completion/interrupt exit mappings remain
unchanged. This is scoped C/D progress, not release or whole-lane acceptance.
