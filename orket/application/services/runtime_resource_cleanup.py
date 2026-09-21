"""Attempt every declared runtime resource close without abandoning native work."""
import asyncio
import inspect
import logging

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread

logger = logging.getLogger(__name__)


async def _close_resources(resources, label):
    failures = []
    for index, target in enumerate(resources):
        try:
            close = getattr(target, "aclose", None) or getattr(target, "close", None)
            if not callable(close):
                continue
            if inspect.iscoroutinefunction(close):
                await close()
            else:
                result = await run_owned_thread(close, label=f"{label}:{index}")
                if inspect.isawaitable(result):
                    await result
        except (Exception, asyncio.CancelledError) as exc:
            # Cleanup supervisor: one failed port must not abandon later resources.
            logger.exception("Runtime cleanup failed (%s, resource %s, type %s)", label, index, type(target).__name__)
            failures.append(exc)
    if len(failures) == 1:
        raise failures[0]
    if failures:
        raise BaseExceptionGroup(f"Runtime cleanup failed: {label}", failures)


async def close_runtime_resources(resources, *, label):
    """Keep the declared order and retain all failures after owned cleanup settles."""
    resources = tuple(resources)
    await run_owned_io(lambda: _close_resources(resources, label), label=label, preserve_failure=True)
