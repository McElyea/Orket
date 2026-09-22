"""Native entrypoint with explicit per-resource or per-call coroutine loop ownership."""

from collections.abc import Coroutine
from typing import Any, TypeVar

from orket.adapters.execution.sync_coroutine_owner import SyncCoroutineOwner, require_native_coroutine

ResultT = TypeVar("ResultT")


side_effecting = True


def run_coro_sync(coro: Coroutine[Any, Any, ResultT], *, owner: SyncCoroutineOwner | None = None) -> ResultT:
    require_native_coroutine(coro)
    if owner is not None:
        if not isinstance(owner, SyncCoroutineOwner):
            coro.close()
            raise TypeError("E_SYNC_COROUTINE_OWNER_REQUIRED")
        return owner.run(coro)
    with SyncCoroutineOwner() as operation:
        return operation.run(coro)
