"""Retain protocol-ledger synchronous file work through interruption."""
from collections.abc import Callable
from functools import partial
from typing import ParamSpec, TypeVar

from orket.adapters.execution.owned_io import run_owned_thread

OperationArgs = ParamSpec("OperationArgs")
OperationResult = TypeVar("OperationResult")

side_effecting = True


async def owned_protocol_io(operation: Callable[OperationArgs, OperationResult], /,
                            *args: OperationArgs.args, **kwargs: OperationArgs.kwargs) -> OperationResult:
    return await run_owned_thread(partial(operation, *args, **kwargs), label="protocol-ledger-file-operation")
