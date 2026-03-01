from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any


class AsyncExecutorService:
    """
    Sync/async boundary helper.

    This centralizes coroutine execution for sync callers so async bridging
    behavior is explicit and reusable across adapters.
    """

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="orket-async-bridge")

    def run_coroutine_blocking(self, coro: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        return self._executor.submit(lambda: asyncio.run(coro)).result()


_DEFAULT_EXECUTOR_SERVICE = AsyncExecutorService()


def run_coroutine_blocking(coro: Any) -> Any:
    return _DEFAULT_EXECUTOR_SERVICE.run_coroutine_blocking(coro)
