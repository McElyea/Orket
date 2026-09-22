"""Retain protocol-ledger synchronous file work through interruption."""
from functools import partial

from orket.adapters.execution.owned_io import run_owned_thread

side_effecting = True


async def owned_protocol_io(operation, /, *args, **kwargs):
    return await run_owned_thread(partial(operation, *args, **kwargs), label="protocol-ledger-file-operation")
