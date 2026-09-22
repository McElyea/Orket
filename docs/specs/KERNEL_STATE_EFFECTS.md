# Kernel local state inputs and effects

Last updated: 2026-09-22
Status: Active implementation contract since 0.6.80; scoped acceptance belongs to the architectural-truth plan

LSI staging, reads, validation, promotion and explicit ledger repair are native
filesystem operations owned by their application caller. Direct calls on a running
event loop refuse before filesystem access. Async callers use the existing owned
Kernel invocation/publication path and retain it through cancellation and close.
An interrupted caller must inspect retained state before retrying.

Each LSI instance captures an absolute lexical root at construction. Promotion and
ledger repair capture their root before filesystem inspection. Bound Kernel owner
and invocation roots follow `KERNEL_RUN_INPUTS.md`. Later cwd changes do not select
another root. Root capture does not resolve links or create files.

Staging detaches all body, links and manifest values and canonicalizes them before
the first effect. Immutable canonical bytes determine object digests, DTO type,
triplet records and reference sources. Caller mutation during a write cannot mix
an earlier object digest with a later body or reference value. Equal captured
inputs produce equal plans; the application owns reading and publishing state.

One classified filesystem adapter executes native reads, writes, copies, renames
and cleanup. Shared layout and reference rules have one definition. Path operands
are absolute; identifier path segments cannot be dot/parent segments and stems
cannot escape the triplet namespace lexically. This is not symlink confinement,
hostile-code containment or caller path authorization. Trusted callers may select
their own absolute workspace. Concurrent external writers remain unsupported.

Promotion validates ledger ordering before deciding whether there is work. Missing
or empty staging with no tombstones is a no-op: advance the ledger and emit
`I_NOOP_PROMOTION`, preserving other committed bytes and file modification times.
Absence is not deletion authorization. Deletion requires a valid staged tombstone;
the tombstone's stem must match its filename and its turn must match the promotion.
This corrects the legacy missing-staging deletion behavior and the old law test
that claimed tombstone coverage without staging one. Archived requirements remain
historical; this document owns the current correction.

Filesystem failures must remain visible. Unreadable/corrupt observed index records
cannot be silently discarded. Promotion reports its existing typed failure outcome
and retains recovery evidence; cleanup failures are separately disclosed. Existing
candidate or backup directories require operator recovery before another promotion;
they are not silently erased or adopted by a new attempt. This applies to no-ops too.
Directory replacement is a multi-step operation, not a crash-atomic transaction.
Neither a failed promotion nor cancellation proves rollback. There is no new
cross-process serialization, durable run recovery or exactly-once guarantee.

The native guard reports `E_KERNEL_STATE_REQUIRES_ASYNC_OWNER`. Invalid adapter
paths/bytes report `E_KERNEL_STATE_ABSOLUTE_PATH_REQUIRED` or
`E_KERNEL_STATE_IMMUTABLE_BYTES_REQUIRED`; invalid namespace values report
`E_KERNEL_STATE_INVALID_PATH_SEGMENT` or `E_KERNEL_STATE_INVALID_STEM`.
Invalid observed record shapes use `E_KERNEL_STATE_INDEX_UNAVAILABLE`; native
read/decode exceptions can also propagate. Promotion retains `E_PROMOTION_FAILED`
and adds `E_PROMOTION_CLEANUP_FAILED` when its cleanup also fails. Reserved recovery
directories report `E_KERNEL_PROMOTION_RECOVERY_REQUIRED` within the failure detail.

The canonical plan must bind real source and installed staging, reads, promotion,
tombstone/no-op behavior, invalid paths, native failures, interruption and shutdown
to the exact artifacts. Independent SQLite responsiveness retains its predeclared
0.5-second bound. Linux clock acceptance, complete adapter/async inventories,
E/CAP and explicit whole-lane acceptance remain separate requirements.
