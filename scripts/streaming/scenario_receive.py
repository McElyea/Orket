"""Own one pending TestClient receive across scenario polling deadlines."""
from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from concurrent.futures import CancelledError
from contextlib import contextmanager
from typing import Any

from anyio import ClosedResourceError, EndOfStream
from starlette.websockets import WebSocketDisconnect


class ScenarioReceiver:
    def __init__(self, socket: Any) -> None:
        self._socket = socket
        self._result: queue.Queue = queue.Queue(maxsize=1)
        self._thread: threading.Thread | None = None

    def _receive(self) -> None:
        try:
            self._result.put((True, self._socket.receive_json()))
        except Exception as exc:  # Thread boundary: transport failures are re-raised by the owner.
            self._result.put((False, exc))

    def receive(self, timeout_s: float) -> dict[str, Any] | None:
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._receive, name="orket-scenario-receive", daemon=True,
            )
            self._thread.start()
        self._thread.join(timeout=max(0.0, timeout_s))
        if self._thread.is_alive():
            return None
        self._thread = None
        ok, value = self._result.get_nowait()
        if not ok:
            raise value
        return value

    def settle(self) -> None:
        """Called after WebSocket context exit releases a blocked receive."""
        if self._thread is None:
            return
        self._thread.join(timeout=5.0)
        if self._thread.is_alive():
            raise RuntimeError("scenario WebSocket receive did not settle after socket closure")
        self._thread = None
        ok, value = self._result.get_nowait()
        if not ok and not isinstance(value, (CancelledError, ClosedResourceError, EndOfStream, WebSocketDisconnect)):
            raise value


@contextmanager
def scenario_socket(connection: Any) -> Iterator[ScenarioReceiver]:
    receiver = None
    try:
        with connection as socket:
            receiver = ScenarioReceiver(socket)
            yield receiver
    finally:
        if receiver is not None:
            receiver.settle()
