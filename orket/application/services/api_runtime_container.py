from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orket.application.services.command_process_supervisor import CommandProcessCancelled
from orket.core.contracts.owned_command import CommandExecutionUncertain

LOGGER = logging.getLogger(__name__)
_REQUEST_OWNER: ContextVar[asyncio.Task[Any] | None] = ContextVar("orket_api_request_owner", default=None)


class ApiRequestAdmissionClosed(RuntimeError):
    """The application stopped admitting request invocations before dispatch."""


@dataclass(frozen=True)
class _RequestOutcome:
    # Task cancellation exceptions are consumed on observation. Retain the exact
    # cleanup outcome so both the request waiter and teardown see uncertainty.
    error: BaseException | None = None


@dataclass
class ApiRuntimeContainer:
    """Application-owned runtime owners and lifecycle for one API app."""

    project_root: Path
    api_runtime_node: Any
    runtime_state: Any
    api_runtime_host: Any
    engine: Any
    authentication: Any | None = None
    system_queries: Any | None = None
    stream_bus: Any | None = None
    interaction_manager: Any | None = None
    extension_manager: Any | None = None
    extension_runtime_service: Any | None = None
    outward_run_store: Any | None = None
    outward_run_event_store: Any | None = None
    outward_approval_store: Any | None = None
    outward_run_service: Any | None = None
    outward_approval_service: Any | None = None
    outward_run_execution_service: Any | None = None
    outward_run_inspection_service: Any | None = None
    outward_ledger_service: Any | None = None
    model_selection: Any | None = None
    governed_agent_runtime: Any | None = None
    _background_tasks: set[asyncio.Task[Any]] = field(default_factory=set, repr=False)
    _cancellation_requests: set[asyncio.Task[Any]] = field(default_factory=set, repr=False)
    _request_tasks: set[asyncio.Task[Any]] = field(default_factory=set, repr=False)
    _owned_resources: list[Any] = field(default_factory=list, repr=False)
    _closed: bool = field(default=False, repr=False)
    _close_task: asyncio.Task[None] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()

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
        return self._close_task is None

    def track_background_task(self, task: asyncio.Task[Any]) -> None:
        if not self.accepting_work:
            task.cancel()
            raise RuntimeError("API runtime container is closed.")
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
            raise RuntimeError("API runtime container is closed.")
        if resource not in self._owned_resources:
            self._owned_resources.append(resource)

    async def run_request(self, invoke: Callable[[], Awaitable[None]]) -> None:
        if not self.accepting_work:
            raise ApiRequestAdmissionClosed("API runtime is closing.")
        task = asyncio.create_task(_invoke_request(invoke), name="orket-api-request")
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
        if (asyncio.current_task() in self._background_tasks or asyncio.current_task() is self._close_task
                or _REQUEST_OWNER.get() in self._request_tasks):
            raise RuntimeError("An API-owned task cannot await its own teardown.")
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._teardown(), name="orket-api-teardown")
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
        errors: list[BaseException] = []
        tasks = [task for task in self._background_tasks | self._request_tasks if not task.done()]
        for task in tasks:
            # A pending cancellation may belong to an internal timeout that will
            # consume it. This owner must issue its own request once at teardown.
            self._cancel_owned_task(task)
        if tasks:
            try:
                results = await asyncio.gather(*(_wait_owned_task(task) for task in tasks))
                errors.extend(error for error in results if error is not None)
            except asyncio.CancelledError as exc:
                LOGGER.exception("API teardown owner interrupted while waiting for owned tasks")
                errors.append(exc)
        self._background_tasks.difference_update(task for task in tasks if task.done())
        self._cancellation_requests.difference_update(task for task in tasks if task.done())

        for resource in reversed(self._owned_resources):
            try:
                await _close_resource(resource)
            except (Exception, asyncio.CancelledError) as exc:  # lifecycle boundary still closes peers
                LOGGER.exception("API-owned resource teardown failed", extra={"resource_type": type(resource).__name__})
                errors.append(exc)
        try:
            await _close_resource(self.engine)
        except (Exception, asyncio.CancelledError) as exc:  # lifecycle boundary reports all close attempts
            LOGGER.exception("API engine teardown failed")
            errors.append(exc)
        if errors:
            raise RuntimeError(f"API runtime teardown failed for {len(errors)} owner(s).") from errors[0]
        self._background_tasks.clear()
        self._request_tasks.clear()
        self._owned_resources.clear()
        self._closed = True


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
    except CommandProcessCancelled as exc:
        if not exc.lifetime.cleanup_confirmed:
            LOGGER.error("API owned command cleanup is unconfirmed", extra={"task_name": task.get_name()})
            return CommandExecutionUncertain(exc.lifetime)
    except asyncio.CancelledError:
        pass  # Cooperative task completion is not proof of durable effect outcome.
    except Exception as exc:  # application shutdown boundary records failed owners
        LOGGER.exception("API owned task failed during teardown", extra={"task_name": task.get_name()})
        return exc
    return None


async def _close_resource(resource: Any) -> None:
    close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
    if callable(close):
        result = close()
        if inspect.isawaitable(result):
            await result
