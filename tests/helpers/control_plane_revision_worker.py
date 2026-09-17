"""Native test worker: each process retains its own observed SQLite revision."""
import asyncio
import json
import os
import sys

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
    ControlPlaneExecutionConflictError,
)
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions


def emit(**payload):
    print(json.dumps(payload), flush=True)


async def main():
    path, kind, mode = sys.argv[1:]
    assert kind in {"run", "attempt", "step"} and mode in {"race", "interrupt"}
    repository = AsyncControlPlaneExecutionRepository(path)
    record = await getattr(repository, f"get_{kind}_record")(**{f"{kind}_id": kind})
    emit(event="observed", pid=os.getpid(), record=record.model_dump(mode="json"))
    updates = json.loads(await asyncio.to_thread(sys.stdin.readline))
    incoming = record.model_copy(update=updates)
    if mode == "interrupt":
        async with SQLiteControlPlaneTransactions(path)() as transaction:
            saved = await getattr(transaction.execution, f"save_{kind}_record")(record=incoming)
            emit(event="uncommitted", revision=saved.state_revision)
            assert await asyncio.to_thread(sys.stdin.readline) == "release\n"
        return
    try:
        saved = await getattr(repository, f"save_{kind}_record")(record=incoming)
    except ControlPlaneExecutionConflictError as exc:
        emit(event="refused", error=str(exc))
    else:
        emit(event="saved", record=saved.model_dump(mode="json"))


if __name__ == "__main__":
    asyncio.run(main())
