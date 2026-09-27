# Shared I/O cancellation ownership

Last updated: 2026-09-25
Status: Active implementation contract; 0.6.106 acceptance remains in the architectural-truth plan

`orket.adapters.execution.owned_io.run_owned_io` retains one admitted operation
until its existing task/gather settlement completes. The operation factory runs
synchronously before the owner's first suspension. Its result must satisfy the
existing `asyncio.create_task` coroutine admission; arbitrary awaitables are not
newly admitted. Factory failures retain their synchronous timing.

Caller cancellation does not abandon admitted work. The first caller
`CancelledError` is retained; repeated requests cannot replace it. With
`cancel_on_interrupt=False`, cancellation is not forwarded to the operation.
With `cancel_on_interrupt=True`, the owner requests child cancellation once and
then retains the child's cleanup through later caller cancellation.

After settlement, an internally cancelled task supplies its original exception
through one result retrieval. The shared owner preserves that cancellation's
identity, subtype, message and existing cause/context when it is the outward
operation failure. No caller cancellation means the exact operation failure is
raised, or its successful value returned. A deliberately returned `BaseException`
value retains the existing failure interpretation.

When the caller was also cancelled, the established precedence remains:

- `preserve_failure=False`: report the operation failure to the existing logger,
  then raise the first caller cancellation.
- `preserve_failure=True`: retain the operation failure outward, including an
  operation cancellation when `cancel_on_interrupt=False`.
- With `cancel_on_interrupt=True`, a cancelled child bypasses operation-failure
  reporting and is treated as interruption cleanup; the first caller cancellation
  remains outward. This policy does
  not infer which cancellation source caused the child to settle.
- A successful operation after caller cancellation is discarded; it cannot
  become successful request publication.

`run_owned_thread` continues to select `preserve_failure=True` without forwarding
cancellation to its native worker. Native failure takes precedence after that
worker settles. The application/Kernel request owners retain their own transport
cancellation and shutdown policies above this shared boundary.

The task's retained cancellation may be consumed by result retrieval. The owner
therefore retrieves it only once, after the shielded gather settles and only
when that task is cancelled. Supported CPython 3.11 and 3.12 source/installed
controls must prove identity and exception graph through the real Kernel path;
structural inspection alone does not prove this runtime behavior.

This contract adds no resource owner, retry, timeout, forced thread stop, rollback
claim or remote-effect guarantee. Existing deadlines, partial-effect records,
required cleanup and finite native-operation bounds remain authoritative.
Migration: `docs/architecture/CONTRACT_DELTA_SHARED_CANCELLATION_D_2026-09-25.md`.
