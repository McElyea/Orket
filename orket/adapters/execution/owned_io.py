"""Retain adapter I/O through caller cancellation until its worker has settled."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

IOResult = TypeVar("IOResult")
logger = logging.getLogger(__name__)


async def run_owned_io(
    operation: Callable[[], Awaitable[IOResult]], *, label: str, preserve_failure: bool = False,
) -> IOResult:
    task = asyncio.create_task(operation())
    joined = asyncio.gather(task, return_exceptions=True)
    cancelled = False
    while True:
        try:
            result, = await asyncio.shield(joined)
            break
        except asyncio.CancelledError:
            # Cancelling an executor await cannot stop its already running thread.
            cancelled = True
    if cancelled:
        if isinstance(result, BaseException):
            logger.warning("Owned I/O failed while draining cancellation (%s)", label,
                           exc_info=(type(result), result, result.__traceback__))
            if preserve_failure:
                # Resource owners must not turn failed cleanup into clean cancellation.
                raise result
        raise asyncio.CancelledError
    if isinstance(result, BaseException):
        raise result
    return result


async def run_owned_thread(operation: Callable[[], IOResult], *, label: str) -> IOResult:
    """Drain a synchronous capability; a worker failure takes precedence over cancellation."""
    return await run_owned_io(lambda: asyncio.to_thread(operation), label=label, preserve_failure=True)
