# Run-start directory publication and interruption

Last updated: 2026-09-19
Status: Active implementation contract; scoped proof and acceptance remain in the architectural-truth plan.

## Summary

- Owner: Orket runtime; architectural-truth D.
- Affected contracts: initial session-bootstrap artifacts and epic startup interruption.
- Effective version: 0.6.33, patch checkpoint within the current breaking extension-origin release.

## Delta

Previously, one directory replace published `runtime_contracts_staging`. A native
Windows access refusal stopped initialization, and cancellation could return while
the `asyncio.to_thread` bootstrap worker continued writing. The retained source
gate contains two actual Windows error 5 failures. Their original holder remains
unknown; a controlled member-file handle independently reproduces that error.

Runtime bootstrap now authorizes a two-second monotonic retry budget for the
side-effecting `adapters.storage.run_start_publication` adapter. Only native Windows
permission errors 5 and 32 retry, at intervals up to 50 milliseconds. This budget
bounds retry admission, not a potentially stalled operating-system call. It is
operational elapsed time, not a new run timestamp or deterministic decision input.
Other errors propagate immediately. The same completed staging directory is
renamed each time; artifacts and their captured timestamp are not regenerated.

An existing destination, including a dangling symlink, refuses with
`E_RUN_START_ARTIFACTS_PUBLISH_CONFLICT`. Exclusive staging creation excludes other
cooperating bootstrap writers. Rename success is checked against the original
directory's device/inode identity and staging absence before returning paths.
This does not attest content bytes against concurrent external writers or provide
a hostile-filesystem boundary. POSIX permits renaming open files/directories;
an open handle alone does not require retry there.

The first native refusal logs `E_RUN_START_ARTIFACTS_PUBLISH_RETRY`; verified rename
after retry logs `RUN_START_ARTIFACTS_PUBLISHED_AFTER_RETRY`. Exhaustion raises
`E_RUN_START_ARTIFACTS_PUBLISH_BLOCKED`, retaining the native error as its cause.
Staging remains and a later ordinary bootstrap refuses it as incomplete. A failed
identity verification raises `E_RUN_START_ARTIFACTS_PUBLISH_UNVERIFIED`; a completed
rename may already exist. None of these failures claims rollback or workload success.

Epic startup captures `RuntimeInputService.utc_now()` before dispatch and retains
the whole bootstrap worker through repeated cancellation or caller timeout. A
worker failure takes precedence over cancellation and the run boundary reports
unresolved truth. Successful publication followed by cancellation can leave final
bootstrap files without a run-ledger entry: cancellation prevents subsequent
startup steps, not effects already completed by the worker. There is no automatic
resume, staging deletion or failed-artifact repair in this change.

## Migration and validation

No artifact schema changes or compatibility shim are introduced. Embedded sync
callers must run capture before entering an event loop or inside an owned worker.
Operators must preserve incomplete evidence and diagnose it before selecting a
new run identity; closing a handle alone does not authorize replay of old staging.

Required proof includes native directory/member handles with release and persistent
refusal, independently compared file bytes, destination conflict, real pipeline
cancellation/timeout with worker success and failure, existing bootstrap contracts,
and native CLI lifecycle. Source and fresh installed Windows/Linux Python 3.11/3.12
gates bind the candidate. The canonical plan records actual results; this document
does not declare those gates complete or explain the original holder.

## Rollback and remaining scope

If publication or interruption proof fails, retain the failed gate and stop checkpoint
acceptance. Code rollback does not undo renamed directories or repair staging.
SDK child lifetime, transitive extension imports, remaining D effects and full-lane
acceptance remain separate obligations.
