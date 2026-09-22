"""Own a native caller's coroutine loop, context and cleanup without a daemon thread."""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from collections.abc import Callable, Coroutine
from contextvars import copy_context
from typing import Any, TypeVar

from orket.adapters.execution.owned_io import require_sync_context

side_effecting = True  # Runs admitted native coroutine operations and owns their loop resources.
LOGGER = logging.getLogger(__name__)
ResultT = TypeVar("ResultT")


def require_native_coroutine(coroutine: Coroutine[Any, Any, ResultT]) -> None:
    if not inspect.iscoroutine(coroutine):
        raise TypeError("run_coro_sync expects a native coroutine object.")
    if inspect.getcoroutinestate(coroutine) != inspect.CORO_CREATED:
        raise ValueError("E_SYNC_COROUTINE_UNSTARTED_REQUIRED")
    try:
        require_sync_context(code="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER")
    except RuntimeError:
        coroutine.close()
        raise


class SyncCoroutineOwner:
    """Serialize one resource's native operations on the same explicitly closed loop."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._closing = threading.Event()
        self._runner: asyncio.Runner | None = None
        self._closed = False
        self._close_failure: BaseException | None = None
        self._loop_errors: list[BaseException] = []

    @property
    def accepting(self) -> bool:
        return not self._closing.is_set()

    @property
    def closed(self) -> bool:
        return self._closed

    def run(self, coroutine: Coroutine[Any, Any, ResultT]) -> ResultT:
        require_native_coroutine(coroutine)
        try:
            if not self.accepting:
                raise RuntimeError("E_SYNC_COROUTINE_OWNER_CLOSED")
            with self._lock:
                if not self.accepting:
                    raise RuntimeError("E_SYNC_COROUTINE_OWNER_CLOSED")
                # Context belongs to this invocation, not to the first caller of the loop.
                return self._owned_runner().run(coroutine, context=copy_context())
        except BaseException:
            # Dispose of an unadmitted coroutine at this ownership boundary on every failure.
            if inspect.getcoroutinestate(coroutine) == inspect.CORO_CREATED:
                coroutine.close()
            raise

    def close(self, finalizer: Callable[[], Coroutine[Any, Any, Any]] | None = None) -> None:
        require_sync_context(code="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER")
        self._closing.set()
        with self._lock:
            if self._closed:
                if self._close_failure is not None:
                    raise self._close_failure
                return
            errors: list[BaseException] = []
            if finalizer is not None:
                try:
                    coroutine = finalizer()
                    require_native_coroutine(coroutine)
                    try:
                        self._owned_runner().run(coroutine, context=copy_context())
                    finally:
                        if inspect.getcoroutinestate(coroutine) == inspect.CORO_CREATED:
                            coroutine.close()
                except BaseException as exc:
                    # Finalizer failure cannot skip loop/async-generator/executor cleanup.
                    errors.append(exc)
            try:
                if self._runner is not None:
                    self._runner.close()
            except BaseException as exc:
                # Native resource supervisor: preserve cleanup failure for the caller.
                errors.append(exc)
            finally:
                self._closed = True
            errors.extend(error for error in self._loop_errors if all(error is not found for found in errors))
            if errors:
                self._close_failure = (
                    errors[0]
                    if len(errors) == 1
                    else BaseExceptionGroup("Synchronous coroutine cleanup failed", errors)
                )
                raise self._close_failure

    def _owned_runner(self) -> asyncio.Runner:
        if self._runner is None:
            # An explicit factory avoids changing the native caller's ambient event-loop binding.
            runner = asyncio.Runner(loop_factory=asyncio.new_event_loop)
            runner.get_loop().set_exception_handler(self._observe_loop_failure)
            self._runner = runner
        return self._runner

    def _observe_loop_failure(self, _loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        error = context.get("exception")
        if not isinstance(error, BaseException):
            error = RuntimeError(str(context.get("message") or "Owned loop reported an unhandled failure"))
        self._loop_errors.append(error)
        LOGGER.error("Owned coroutine loop failure", exc_info=(type(error), error, error.__traceback__))

    def __enter__(self) -> SyncCoroutineOwner:
        if not self.accepting:
            raise RuntimeError("E_SYNC_COROUTINE_OWNER_CLOSED")
        return self

    def __exit__(self, _kind: Any, failure: BaseException | None, _traceback: Any) -> None:
        try:
            self.close()
        except BaseException as cleanup_failure:
            if failure is not None and cleanup_failure is not failure:
                raise BaseExceptionGroup(
                    "Synchronous coroutine operation and cleanup failed", [failure, cleanup_failure]
                ) from None
            raise
