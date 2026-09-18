from __future__ import annotations

import asyncio
import inspect
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, ClassVar

from orket.application.services.command_process_supervisor import CommandProcessCancelled
from orket.core.contracts.owned_command import CommandExecutionUncertain

LOGGER = logging.getLogger(__name__)
_REQUEST_OWNER: ContextVar[asyncio.Task[Any] | None] = ContextVar("orket_application_request_owner", default=None)


class RequestAdmissionClosed(RuntimeError):
    """The application stopped admitting invocations before dispatch."""


@dataclass(frozen=True)
class _RequestOutcome:
    # Task cancellation exceptions are consumed on observation. Retain the exact
    # cleanup outcome so both the request waiter and teardown see uncertainty.
    error: BaseException | None = None


@dataclass(eq=False)
class ApplicationRuntimeLifetime(ABC):
    """One application-owned request, background-task and resource lifetime."""

    _runtime_name: ClassVar[str] = "Application"
    _admission_error: ClassVar[type[RequestAdmissionClosed]] = RequestAdmissionClosed
    _background_tasks: set[asyncio.Task[Any]] = field(default_factory=set, repr=False, init=False)
    _cancellation_requests: set[asyncio.Task[Any]] = field(default_factory=set, repr=False, init=False)
    _request_tasks: set[asyncio.Task[Any]] = field(default_factory=set, repr=False, init=False)
    _owned_resources: list[Any] = field(default_factory=list, repr=False, init=False)
    _closed: bool = field(default=False, repr=False, init=False)
    _close_task: asyncio.Task[None] | None = field(default=None, repr=False, init=False)
    _background_failure: BaseException | None = field(default=None, repr=False, init=False)

    @property
    def active_background_task_count(self) -> int:
        return sum(1 for task in self._background_tasks if not task.done())

    @property
    def active_request_count(self) -> int:
        return sum(1 for task in self._request_tasks if not task.done())

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def accepting_work(self) -> bool:
        return self._close_task is None and self._background_failure is None

    def track_background_task(self, task: asyncio.Task[Any]) -> None:
        if not self.accepting_work:
            task.cancel()
            raise RuntimeError(f"{self._runtime_name} runtime container is closed.")
        self._background_tasks.add(task)

    def release_background_task(self, task: asyncio.Task[Any]) -> None:
        self._background_tasks.discard(task)
        if task.done():
            self._cancellation_requests.discard(task)

    def _cancel_owned_task(self, task: asyncio.Task[Any]) -> None:
        if not task.done() and task not in self._cancellation_requests:
            self._cancellation_requests.add(task)
            task.cancel()

    def register_owned_resource(self, resource: Any) -> None:
        if not self.accepting_work:
            raise RuntimeError(f"{self._runtime_name} runtime container is closed.")
        if resource not in self._owned_resources:
            self._owned_resources.append(resource)

    def release_owned_resource(self, resource: Any) -> None:
        """Transfer a resource to an already-running owned task before its first await."""
        self._owned_resources.remove(resource)

    def start_background(self, invoke: Callable[[], Awaitable[None]]) -> asyncio.Task[Any]:
        """Admit before invocation; retain failure even when work ends before shutdown."""
        if not self.accepting_work:
            raise self._admission_error(f"{self._runtime_name} runtime is closing.")
        task = asyncio.create_task(_invoke_request(invoke), name=f"orket-{self._runtime_name.lower()}-background")
        self.track_background_task(task)
        task.add_done_callback(self._background_settled)
        return task

    def _background_settled(self, task: asyncio.Task[Any]) -> None:
        try:
            outcome = task.result()
            error = outcome.error
        except (Exception, asyncio.CancelledError) as exc:  # background supervisor observes pre-start cancellation
            error = exc
        failure = _owned_failure(error)
        if failure is not None:
            self._background_failure = self._background_failure or failure
            LOGGER.error(
                "Application background task failed",
                extra={"task_name": task.get_name()},
                exc_info=(type(failure), failure, failure.__traceback__),
            )
        self.release_background_task(task)

    async def run_request(self, invoke: Callable[[], Awaitable[None]]) -> None:
        if not self.accepting_work:
            raise self._admission_error(f"{self._runtime_name} runtime is closing.")
        task = asyncio.create_task(_invoke_request(invoke), name=f"orket-{self._runtime_name.lower()}-request")
        self._request_tasks.add(task)
        cancelled = None
        try:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError as exc:
                    self._cancel_owned_task(task)
                    cancelled = cancelled or exc
            outcome = task.result()
            if outcome.error is not None:
                if cancelled is not None and type(outcome.error) is asyncio.CancelledError:
                    # Keep the transport's cancellation scope identity after local
                    # cleanup; typed command uncertainty still takes precedence.
                    raise cancelled
                raise outcome.error
            if cancelled is not None:
                raise cancelled
        finally:
            self._request_tasks.discard(task)
            self._cancellation_requests.discard(task)

    async def close(self) -> None:
        if (
            asyncio.current_task() in self._background_tasks
            or asyncio.current_task() is self._close_task
            or _REQUEST_OWNER.get() in self._request_tasks | self._background_tasks
        ):
            raise RuntimeError(f"An {self._runtime_name}-owned task cannot await its own teardown.")
        if self._close_task is None:
            self._close_task = asyncio.create_task(
                self._teardown(), name=f"orket-{self._runtime_name.lower()}-teardown"
            )
        cancelled = None
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError as exc:
                cancelled = cancelled or exc
        # Retain failure for every caller, including later calls on another loop.
        # A failed teardown takes precedence over cancellation of a close waiter.
        self._close_task.result()
        if cancelled is not None:
            raise cancelled

    async def _teardown(self) -> None:
        errors: list[BaseException] = [self._background_failure] if self._background_failure is not None else []
        # A completed background wrapper may still have its observation callback
        # queued. Consume its result here as well before releasing resources.
        tasks = list(self._background_tasks | {task for task in self._request_tasks if not task.done()})
        for task in tasks:
            # A pending cancellation may belong to an internal timeout that will
            # consume it. This owner must issue its own request once at teardown.
            self._cancel_owned_task(task)
        if tasks:
            try:
                results = await asyncio.gather(*(_wait_owned_task(task) for task in tasks))
                errors.extend(error for error in results if error is not None)
            except asyncio.CancelledError as exc:
                LOGGER.exception("%s teardown owner interrupted while waiting for owned tasks", self._runtime_name)
                errors.append(exc)
        self._background_tasks.difference_update(task for task in tasks if task.done())
        self._cancellation_requests.difference_update(task for task in tasks if task.done())

        for resource in reversed(self._owned_resources):
            try:
                await close_owned_resource(resource)
            except (Exception, asyncio.CancelledError) as exc:  # lifecycle boundary still closes peers
                LOGGER.exception(
                    "Application-owned resource teardown failed", extra={"resource_type": type(resource).__name__}
                )
                errors.append(exc)
        try:
            await self._close_final_resource()
        except (Exception, asyncio.CancelledError) as exc:  # lifecycle boundary reports all close attempts
            LOGGER.exception("%s final resource teardown failed", self._runtime_name)
            errors.append(exc)
        if errors:
            raise RuntimeError(f"{self._runtime_name} runtime teardown failed for {len(errors)} owner(s).") from errors[
                0
            ]
        self._background_tasks.clear()
        self._request_tasks.clear()
        self._owned_resources.clear()
        self._closed = True

    @abstractmethod
    async def _close_final_resource(self) -> None:
        """Close the application's final resource after tasks and registered peers."""
        raise NotImplementedError


async def _invoke_request(invoke: Callable[[], Awaitable[None]]) -> _RequestOutcome:
    token = _REQUEST_OWNER.set(asyncio.current_task())
    try:
        await invoke()
        return _RequestOutcome()
    except (Exception, asyncio.CancelledError) as exc:  # request supervisor retains failure for both observers
        return _RequestOutcome(exc)
    finally:
        _REQUEST_OWNER.reset(token)


async def _wait_owned_task(task: asyncio.Task[Any]) -> BaseException | None:
    try:
        result = await task
        if isinstance(result, _RequestOutcome) and result.error is not None:
            raise result.error
    except (Exception, asyncio.CancelledError) as exc:  # application shutdown boundary records failed owners
        failure = _owned_failure(exc)
        if failure is not None:
            LOGGER.error(
                "Application owned task failed during teardown",
                extra={"task_name": task.get_name()},
                exc_info=(type(failure), failure, failure.__traceback__),
            )
        return failure
    return None


def _owned_failure(error: BaseException | None) -> BaseException | None:
    if isinstance(error, CommandProcessCancelled):
        return None if error.lifetime.cleanup_confirmed else CommandExecutionUncertain(error.lifetime)
    if isinstance(error, asyncio.CancelledError):
        return None  # Cooperative completion does not establish a successful durable effect.
    return error


async def close_owned_resource(resource: Any) -> None:
    close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
    if callable(close):
        result = close()
        if inspect.isawaitable(result):
            await result
