# orket/state.py
import asyncio
from typing import Any


class GlobalState:
    """Global singleton for cross-module coordination."""

    def __init__(self):
        self.interventions: dict[str, dict[str, str]] = {}
        self.event_queue = asyncio.Queue()
        self.active_websockets: list[Any] = []
        self.active_tasks: dict[str, list[asyncio.Task[Any]]] = {}

        # Locks are created at import time. This is safe on Python 3.11 because
        # asyncio locks no longer bind to a running loop at construction time.
        # Tests that replace loop-scoped state should also create a fresh GlobalState.
        self._ws_lock = asyncio.Lock()
        self._tasks_lock = asyncio.Lock()
        self._interventions_lock = asyncio.Lock()

    async def add_websocket(self, ws: Any) -> None:
        async with self._ws_lock:
            self.active_websockets.append(ws)

    async def remove_websocket(self, ws: Any) -> None:
        async with self._ws_lock:
            if ws in self.active_websockets:
                self.active_websockets.remove(ws)

    async def get_websockets(self) -> list[Any]:
        async with self._ws_lock:
            return list(self.active_websockets)

    async def add_task(self, session_id: str, task: asyncio.Task) -> None:
        async with self._tasks_lock:
            self.active_tasks.setdefault(session_id, []).append(task)

    async def remove_task(self, session_id: str, task: asyncio.Task | None = None) -> None:
        async with self._tasks_lock:
            tasks = self.active_tasks.get(session_id)
            if not tasks:
                return
            if task is None:
                self.active_tasks.pop(session_id, None)
                return
            remaining = [active_task for active_task in tasks if active_task is not task]
            if remaining:
                self.active_tasks[session_id] = remaining
                return
            self.active_tasks.pop(session_id, None)

    async def get_tasks(self, session_id: str) -> list[asyncio.Task[Any]]:
        async with self._tasks_lock:
            return list(self.active_tasks.get(session_id, []))

    async def get_task(self, session_id: str) -> asyncio.Task | None:
        async with self._tasks_lock:
            tasks = list(self.active_tasks.get(session_id, []))
            for task in reversed(tasks):
                if not task.done():
                    return task
            return tasks[-1] if tasks else None

    async def get_active_task_count(self) -> int:
        async with self._tasks_lock:
            return sum(1 for tasks in self.active_tasks.values() for task in tasks if not task.done())

    async def set_intervention(self, session_id: str, intervention: dict[str, str]) -> None:
        async with self._interventions_lock:
            self.interventions[session_id] = dict(intervention)

    async def get_intervention(self, session_id: str) -> dict[str, str] | None:
        async with self._interventions_lock:
            value = self.interventions.get(session_id)
            return dict(value) if value is not None else None

    async def remove_intervention(self, session_id: str) -> None:
        async with self._interventions_lock:
            self.interventions.pop(session_id, None)

    async def get_interventions(self) -> dict[str, dict[str, str]]:
        async with self._interventions_lock:
            return {key: dict(value) for key, value in self.interventions.items()}


runtime_state = GlobalState()
