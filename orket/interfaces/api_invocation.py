"""Captured API invocation and existing task bookkeeping."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from typing import Any, cast

from fastapi import HTTPException

from orket.application.services import api_policy_input_service as api_policy


def resolve_api_method(target: object, invocation: dict[str, Any], error_prefix: str) -> Callable[..., Any]:
    method_name = invocation["method_name"]
    method = getattr(target, method_name, None)
    if method is None or not callable(method):
        detail = invocation.get("unsupported_detail")
        if detail:
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=400, detail=f"Unsupported {error_prefix} method '{method_name}'.")
    return cast(Callable[..., Any], method)


async def invoke_api_method(target: object, invocation: dict[str, Any], error_prefix: str) -> Any:
    invocation = api_policy.capture_api_invocation(invocation)
    method = resolve_api_method(target, invocation, error_prefix)
    return await method(*invocation.get("args", []), **invocation.get("kwargs", {}))


async def schedule_api_invocation_task(
    target: object,
    invocation: dict[str, Any],
    error_prefix: str,
    session_id: str,
    *, runtime_getter,
) -> None:
    invocation = api_policy.capture_api_invocation(invocation)
    method = resolve_api_method(target, invocation, error_prefix)
    task = asyncio.create_task(method(*invocation.get("args", []), **invocation.get("kwargs", {})))
    context = runtime_getter()
    state = runtime_getter().runtime_state
    context.track_background_task(task)
    await state.add_task(session_id, task)
    loop = asyncio.get_running_loop()

    # Always remove completed/canceled tasks to keep active task tracking accurate.
    def _cleanup(_done_task: asyncio.Task[Any]) -> None:
        async def _release_task() -> None:
            await state.remove_task(session_id, task)
            context.release_background_task(task)

        def _start_cleanup() -> None:
            if not context.accepting_work:
                return
            cleanup_task = asyncio.create_task(_release_task())
            context.track_background_task(cleanup_task)
            cleanup_task.add_done_callback(context.release_background_task)

        with suppress(RuntimeError):
            loop.call_soon_threadsafe(_start_cleanup)

    task.add_done_callback(_cleanup)
