from __future__ import annotations

import asyncio
import threading
from typing import Any

_bridge_lock = threading.Lock()
_bridge_ready = threading.Event()
_bridge_loop: asyncio.AbstractEventLoop | None = None
_bridge_thread: threading.Thread | None = None


def _bridge_loop_runner(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    _bridge_ready.set()
    loop.run_forever()


def _ensure_bridge_loop() -> asyncio.AbstractEventLoop:
    global _bridge_loop, _bridge_thread
    with _bridge_lock:
        if (
            _bridge_loop is not None
            and _bridge_thread is not None
            and _bridge_thread.is_alive()
            and not _bridge_loop.is_closed()
        ):
            return _bridge_loop

        _bridge_ready.clear()
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=_bridge_loop_runner,
            args=(loop,),
            name="orket-sync-bridge-loop",
            daemon=True,
        )
        thread.start()
        if not _bridge_ready.wait(timeout=5.0):
            raise RuntimeError("Failed to start sync bridge event loop thread.")
        _bridge_loop = loop
        _bridge_thread = thread
        return loop


def run_coro_sync(coro: Any) -> Any:
    if not asyncio.iscoroutine(coro):
        raise TypeError("run_coro_sync expects a coroutine object.")
    loop = _ensure_bridge_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
