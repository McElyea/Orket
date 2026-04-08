# orket/state.py
import asyncio
from typing import Any


class GlobalState:
    """Global singleton for transport/runtime coordination."""

    def __init__(self) -> None:
        self.interventions: dict[str, dict[str, str]] = {}
        self.event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.active_websockets: list[Any] = []
        self.active_tasks: dict[str, list[asyncio.Task[Any]]] = {}
        self.interaction_sessions: set[str] = set()

        # Locks are created at import time. This is safe on Python 3.11 because
        # asyncio locks no longer bind to a running loop at construction time.
        # Tests that replace loop-scoped state should also create a fresh GlobalState.
        self._ws_lock = asyncio.Lock()
        self._tasks_lock = asyncio.Lock()
        self._interventions_lock = asyncio.Lock()
        self._interaction_sessions_lock = asyncio.Lock()

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

    async def add_task(self, session_id: str, task: asyncio.Task[Any]) -> None:
        async with self._tasks_lock:
            self.active_tasks.setdefault(session_id, []).append(task)

    async def remove_task(self, session_id: str, task: asyncio.Task[Any] | None = None) -> None:
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

    async def get_task(self, session_id: str) -> asyncio.Task[Any] | None:
        async with self._tasks_lock:
            tasks = list(self.active_tasks.get(session_id, []))
            for task in reversed(tasks):
                if not task.done():
                    return task
            return None

    async def get_active_task_count(self) -> int:
        async with self._tasks_lock:
            return sum(1 for tasks in self.active_tasks.values() for task in tasks if not task.done())

    async def register_interaction_session(self, session_id: str) -> None:
        async with self._interaction_sessions_lock:
            self.interaction_sessions.add(str(session_id))

    async def unregister_interaction_session(self, session_id: str) -> None:
        async with self._interaction_sessions_lock:
            self.interaction_sessions.discard(str(session_id))

    async def is_interaction_session(self, session_id: str) -> bool:
        async with self._interaction_sessions_lock:
            return str(session_id) in self.interaction_sessions

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

    def reset(self) -> None:
        self.interventions = {}
        self.event_queue = asyncio.Queue()
        self.active_websockets = []
        self.active_tasks = {}
        self.interaction_sessions = set()


def create_runtime_state() -> GlobalState:
    return GlobalState()


def reset_runtime_state() -> GlobalState:
    global runtime_state
    runtime_state = create_runtime_state()
    return runtime_state


runtime_state = create_runtime_state()
