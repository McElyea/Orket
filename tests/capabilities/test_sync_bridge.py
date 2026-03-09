from __future__ import annotations

import asyncio

from orket.capabilities.sync_bridge import run_coro_sync


class _LoopBoundProbe:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None

    async def call(self) -> str:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        else:
            if loop is not self._loop:
                raise RuntimeError("loop changed")
            if loop.is_closed():
                raise RuntimeError("loop closed")
        await asyncio.sleep(0)
        return "ok"


def test_run_coro_sync_reuses_persistent_loop() -> None:
    probe = _LoopBoundProbe()
    for _ in range(6):
        assert run_coro_sync(probe.call()) == "ok"


def test_run_coro_sync_inside_running_loop() -> None:
    async def _invoke() -> str:
        return run_coro_sync(asyncio.sleep(0, result="ok"))

    assert asyncio.run(_invoke()) == "ok"
