"""Keep API job registration and failure observation under the application owner."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io
from orket.exceptions import CardNotFound


async def api_target_exists(engine, method_name: str, asset_id: str) -> bool:
    if method_name not in {"run_card", "run_epic", "run_issue", "run_rock"}:
        return True
    try:
        await engine.resolve_run_card_target(asset_id)
    except CardNotFound:
        return False
    return True


@dataclass(eq=False)
class _Registration:
    state: Any
    session_id: str
    task: asyncio.Task | None = None

    async def close(self) -> None:
        if self.task is not None:
            await self.state.remove_task(self.session_id, self.task)


async def schedule_api_job(context, invoke_method, session_id: str) -> None:
    registered = asyncio.Event()
    registration = _Registration(context.runtime_state, session_id)
    # The resource also covers cancellation before the coroutine's first step.
    context.register_owned_resource(registration)

    async def invoke() -> None:
        try:
            await registered.wait()
            await invoke_method()
        finally:
            await run_owned_io(registration.close, label="api-invocation-unregister", preserve_failure=True)
            context.release_owned_resource(registration)

    task = context.start_background(invoke)
    registration.task = task
    admitted = False
    try:
        await context.runtime_state.add_task(session_id, task)
        admitted = True
    finally:
        if not admitted:
            task.cancel()
        registered.set()
