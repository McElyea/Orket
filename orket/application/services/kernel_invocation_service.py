"""Application worker and continuation ownership for synchronous Kernel surfaces."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any, TypeVar

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.application.services.kernel_action_input_service import capture_kernel_request
from orket.application.services.kernel_invocation_inputs import (
    bind_kernel_environment,
    bind_kernel_invocation_root,
    capture_kernel_environment,
    capture_kernel_invocation_root,
)

Result = TypeVar("Result")


async def invoke_kernel(operation: Callable[..., Result], /, *args: Any, **kwargs: Any) -> Result:
    captured = capture_kernel_request({"args": list(args), "kwargs": kwargs})
    environment = capture_kernel_environment()
    root = capture_kernel_invocation_root()
    with bind_kernel_environment(environment), bind_kernel_invocation_root(root):
        return await run_owned_thread(
            partial(operation, *captured["args"], **captured["kwargs"]), label="kernel-invocation"
        )


async def own_kernel_publication(operation: Callable[[], Awaitable[Result]]) -> Result:
    environment = capture_kernel_environment()
    root = capture_kernel_invocation_root()
    with bind_kernel_environment(environment), bind_kernel_invocation_root(root):
        return await run_owned_io(operation, label="kernel-publication", preserve_failure=True)
