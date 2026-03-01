# orket/state.py
import asyncio
from typing import Dict, List, Any


class GlobalState:
    """Global singleton for cross-module coordination."""
    def __init__(self):
        self.interventions: Dict[str, Dict[str, str]] = {}
        self.event_queue = asyncio.Queue()
        self.active_websockets: List[Any] = []
        self.active_tasks: Dict[str, asyncio.Task] = {}

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

    async def get_websockets(self) -> List[Any]:
        async with self._ws_lock:
            return list(self.active_websockets)

    async def add_task(self, session_id: str, task: asyncio.Task) -> None:
        async with self._tasks_lock:
            self.active_tasks[session_id] = task

    async def remove_task(self, session_id: str) -> None:
        async with self._tasks_lock:
            self.active_tasks.pop(session_id, None)

    async def get_task(self, session_id: str) -> asyncio.Task | None:
        async with self._tasks_lock:
            return self.active_tasks.get(session_id)

    async def set_intervention(self, session_id: str, intervention: Dict[str, str]) -> None:
        async with self._interventions_lock:
            self.interventions[session_id] = dict(intervention)

    async def get_intervention(self, session_id: str) -> Dict[str, str] | None:
        async with self._interventions_lock:
            value = self.interventions.get(session_id)
            return dict(value) if value is not None else None

    async def remove_intervention(self, session_id: str) -> None:
        async with self._interventions_lock:
            self.interventions.pop(session_id, None)

    async def get_interventions(self) -> Dict[str, Dict[str, str]]:
        async with self._interventions_lock:
            return {key: dict(value) for key, value in self.interventions.items()}


runtime_state = GlobalState()
