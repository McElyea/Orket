# Shared I/O cancellation ownership

Last updated: 2026-10-04
Status: Active implementation contract; 0.6.106 acceptance remains in the architectural-truth plan

`orket.adapters.execution.owned_io.run_owned_io` retains one admitted operation
until its existing task/gather settlement completes. The operation factory runs
synchronously before the owner's first suspension. Its result must satisfy the
existing `asyncio.create_task` coroutine admission; arbitrary awaitables are not
newly admitted. Factory failures retain their synchronous timing.

`AsyncFileTools.write_file` preserves the serialized text as exact UTF-8 bytes,
without host newline translation. LF, CRLF and mixed submitted endings remain
distinct. Object content retains the existing JSON serialization. The owned
open/write/close lifetime and failure precedence remain unchanged. Text reads
retain their existing universal-newline behavior; byte acceptance captures files
separately and performs no text normalization. Delta:
`docs/architecture/CONTRACT_DELTA_WORKFLOW_RECOVERY_2026-10-04.md`.

`OwnedCoroutine[T]` names that coroutine/generator family. The shared factory,
Kernel publication factory and turn-preparation close port use it instead of
promising admission of arbitrary `Awaitable[T]`. Native async callables satisfy
the declaration. The selected interpreter can still refuse a generator; the
annotation does not override actual Task admission or take ownership of refused
work. The broader `KernelRuntimeLifetime.invoke` awaitable contract remains: its
existing publication coroutine awaits that supplied operation.

Settlement carries the operation result or original failure plus the first caller
cancellation. The adapter's result is generic; exact variadic `throw(*args)`
forwarding remains an unchecked typing boundary. These declarations add no runtime
normalization, admission, retry or cleanup. Callers should accurately annotate
their coroutine-producing factories; do not silently wrap rejected work to admit it.
Typing migration and proof limits:
`docs/architecture/CONTRACT_DELTA_OWNED_IO_TYPING_E1_2026-09-28.md`.

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

`finish_owned_io` and its native `finish_owned_thread` entry share that same
settlement loop. They are for finalization after the caller has selected its
outcome: later caller cancellation is retained through settlement but does not
replace that outcome. An actual operation failure, including its own native
`CancelledError`, is raised exactly for the caller's failure policy. They do not
clear cancellation counts or convert failed publication to a supporting note.
Callers without a selected outcome keep ordinary operation semantics; interrupted
successful cleanup cannot become successful work. Migration and proof limits:
`docs/architecture/CONTRACT_DELTA_REQUIRED_FINALIZERS_D_2026-09-28.md`.

`finish_owned_io` and its native `finish_owned_thread` entry share that same
settlement loop. They are for finalization after the caller has selected its
outcome: later caller cancellation is retained through settlement but does not
replace that outcome. An actual operation failure, including its own native
`CancelledError`, is raised exactly for the caller's failure policy. They do not
clear cancellation counts or convert failed publication to a supporting note.
Callers without a selected outcome keep ordinary operation semantics; interrupted
successful cleanup cannot become successful work. Migration and proof limits:
`docs/architecture/CONTRACT_DELTA_REQUIRED_FINALIZERS_D_2026-09-28.md`.

Every admitted operation is driven through a small coroutine-protocol adapter.
The factory still runs synchronously; values rejected by the existing coroutine
admission are passed unchanged to `asyncio.create_task` for refusal. The adapter
delegates `send`, `throw` and `close` to the admitted coroutine. It does not replace
that protocol with `await operation`, which has different semantics for some
generator and Coroutine-ABC objects accepted by Task. A refusing task factory does
not cause the shared owner to start, close or otherwise consume caller-owned work.

Only `KeyboardInterrupt` and `SystemExit` raised while driving an admitted
coroutine become its exact failure value before the internal Task completes. The
existing settlement and precedence logic then raises the selected failure at the
public caller boundary. This applies again at each enclosing shared owner: a
native fatal failure cannot escape through an outer owner's operation Task before
the outer caller receives it. A caller that does not catch the selected fatal
failure retains its ordinary fatal meaning. Ordinary exceptions, native and async
`CancelledError`, and deliberately returned failure values retain their existing
paths. There is one settlement loop and no added admission or cancellation owner.

This does change the coroutine object visible to a custom task factory. Exact
task-factory object identity, custom Task implementations that require concrete
native coroutine types, and coroutine introspection are not preservation claims.
Python 3.12 eager task factories have not been verified by this change; default
Task controls do not establish eager-factory compatibility.
Supported default-Task behavior and refusal ownership require actual source and
installed controls; a source trace alone cannot establish them.
Contract delta: `docs/architecture/CONTRACT_DELTA_NESTED_FATAL_IO_D_2026-09-28.md`.

The task's retained cancellation may be consumed by result retrieval. The owner
therefore retrieves it only once, after the shielded gather settles and only
when that task is cancelled. Supported CPython 3.11 and 3.12 source/installed
controls must prove identity and exception graph through the real Kernel path;
structural inspection alone does not prove this runtime behavior.

This contract adds no resource owner, retry, timeout, forced thread stop, rollback
claim or remote-effect guarantee. Existing deadlines, partial-effect records,
required cleanup and finite native-operation bounds remain authoritative.
Migration: `docs/architecture/CONTRACT_DELTA_SHARED_CANCELLATION_D_2026-09-25.md`.


The unguarded `ToolRuntimeExecutor.invoke` route uses this same owner around its
existing tool operation and around native synchronous calls. Its deadline requests
cancellation once and retains admitted native work or async cleanup through later
caller cancellation. Native synchronous failure retains precedence; the runtime's
existing error/timeout envelopes still apply. Returned exception objects remain
ordinary tool values through private tuple carriers. The guarded route now composes its existing authority await under the same timeout
owner; one cancellation still reaches that authority. `CardWorkspaceMutationService`
uses the shared owner with failure preservation and no forwarded interruption while holding its
existing guard. The runtime retains synchronous native failure provenance; it does not newly
classify an arbitrary authority's own async `CancelledError` after caller interruption.
Detailed guarded policy: `docs/architecture/CONTRACT_DELTA_GUARDED_MUTATION_OWNERSHIP_D_2026-09-28.md`. Detailed contract and proof
limits: `docs/architecture/CONTRACT_DELTA_TOOL_RUNTIME_OWNERSHIP_D_2026-09-28.md`.
