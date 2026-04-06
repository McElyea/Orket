from __future__ import annotations

import asyncio
from typing import Any, Coroutine, TypeVar

ResultT = TypeVar("ResultT")


class AsyncExecutorService:
    """
    Sync/async boundary helper.

    This centralizes coroutine execution for sync callers so async bridging
    behavior is explicit and reusable across adapters.
    """

    def run_coroutine_blocking(self, coro: Coroutine[Any, Any, ResultT]) -> ResultT:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        raise RuntimeError(
            "run_coroutine_blocking() cannot be used from a running event loop; "
            "convert the caller to async and await the coroutine directly."
        )


_DEFAULT_EXECUTOR_SERVICE = AsyncExecutorService()


def run_coroutine_blocking(coro: Coroutine[Any, Any, ResultT]) -> ResultT:
    return _DEFAULT_EXECUTOR_SERVICE.run_coroutine_blocking(coro)
