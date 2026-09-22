"""Reuse application task ownership for Kernel publications and native close."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, TypeVar

from orket.application.services.application_runtime_lifetime import ApplicationRuntimeLifetime
from orket.application.services.kernel_invocation_inputs import (
    bind_kernel_environment,
    bind_kernel_invocation_root,
    capture_kernel_environment,
    capture_kernel_invocation_root,
)
from orket.application.services.kernel_invocation_service import own_kernel_publication
from orket.application.services.kernel_runtime_owner import KernelRuntime
from orket.application.services.runtime_resource_cleanup import close_runtime_resources

Result = TypeVar("Result")
# Only the exact admitted publication task may join its own continuation.
_admitted: ContextVar[tuple[Any, asyncio.Task[Any] | None] | None] = ContextVar("kernel_admitted_task", default=None)


class KernelRuntimeLifetime(ApplicationRuntimeLifetime):
    _runtime_name = "Kernel"

    def __init__(self, runtime: KernelRuntime) -> None:
        super().__init__()
        self.runtime = runtime

    async def invoke(self, operation: Callable[[], Awaitable[Result]]) -> Result:
        if _admitted.get() == (self, asyncio.current_task()):
            return await operation()
        environment = capture_kernel_environment()
        root = capture_kernel_invocation_root()
        result: list[Result] = []

        async def publish() -> None:
            token = _admitted.set((self, asyncio.current_task()))
            try:
                with self.runtime.activate():
                    result.append(await operation())
            finally:
                _admitted.reset(token)

        async def admitted() -> None:
            await own_kernel_publication(publish)

        with bind_kernel_environment(environment), bind_kernel_invocation_root(root):
            await self.run_request(admitted)
        return result[0]

    async def _close_final_resource(self) -> None:
        await close_runtime_resources((self.runtime,), label="kernel-runtime-close")
