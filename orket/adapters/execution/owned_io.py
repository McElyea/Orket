"""Retain adapter I/O through caller cancellation until its worker has settled."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import partial
from typing import TypeVar

IOResult = TypeVar("IOResult")
logger = logging.getLogger(__name__)
side_effecting = True  # Owns asynchronous I/O and worker admission.


async def run_owned_io(
    operation: Callable[[], Awaitable[IOResult]], *, label: str, preserve_failure: bool = False,
    cancel_on_interrupt: bool = False,
) -> IOResult:
    warn = logger.warning
    result, cancelled = await _settle_owned_io(operation, cancel_on_interrupt=cancel_on_interrupt)
    if cancelled is not None:
        if isinstance(result, BaseException) and not (cancel_on_interrupt and isinstance(result, asyncio.CancelledError)):
            selected = result if preserve_failure else cancelled
            await run_owned_diagnostic(partial(warn, "Owned I/O failed while draining cancellation (%s)", label,
                exc_info=(type(result), result, result.__traceback__)), primary=selected)
            raise selected
        raise cancelled
    if isinstance(result, BaseException):
        raise result
    return result


async def _settle_owned_io(operation, *, cancel_on_interrupt=False):
    """The single admission/settlement loop shared by operations and their finalizers."""
    task = asyncio.create_task(operation())
    joined = asyncio.gather(task, return_exceptions=True)
    cancelled: asyncio.CancelledError | None = None
    while True:
        try:
            result, = await asyncio.shield(joined)
            break
        except asyncio.CancelledError as exc:
            # Cancelling an executor await cannot stop its already running thread.
            # Async resource owners can opt into one cancellation, then retain
            # their cleanup through subsequent caller cancellation requests.
            if cancel_on_interrupt and cancelled is None:
                task.cancel()
            if cancelled is None:
                cancelled = exc
    # gather synthesizes cancellation; retrieve the original from the settled
    # task once, before its retained exception slot is consumed.
    if task.cancelled():
        try:
            task.result()
        except asyncio.CancelledError as exc:
            result = exc
    return result, cancelled


async def run_owned_diagnostic(operation: Callable[[], object], *, primary: BaseException) -> None:
    """Retain a supporting native attempt without replacing its selected failure."""
    async def guarded_attempt() -> bool:
        try:
            await asyncio.to_thread(operation)
        except BaseException:  # Diagnostic supervisor: contain even fatal handler/executor refusal before task completion.
            return False
        return True

    succeeded, _cancelled = await _settle_owned_io(guarded_attempt)
    # Ordinary exception state is borrowed. Do not invoke an overridden note hook,
    # retain a secondary exception, or recursively log this supporting failure.
    marker = "E_OWNED_DIAGNOSTIC_FAILED"
    if succeeded is not True and marker not in getattr(primary, "__notes__", ()):
        BaseException.add_note(primary, marker)


async def run_owned_thread(operation: Callable[[], IOResult], *, label: str) -> IOResult:
    """Drain a synchronous capability; a worker failure takes precedence over cancellation."""
    return await run_owned_io(lambda: asyncio.to_thread(operation), label=label, preserve_failure=True)


def require_sync_context(*, code: str) -> None:
    """Refuse synchronous native work on a running event loop before any effects."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise RuntimeError(code)
