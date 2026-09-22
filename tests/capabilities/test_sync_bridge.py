from __future__ import annotations

import asyncio

import pytest

from orket.adapters.execution.sync_coroutine_owner import SyncCoroutineOwner
from orket.capabilities.sync_bridge import run_coro_sync

pytestmark = pytest.mark.contract

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
    """Layer: contract. An explicit resource owner preserves affinity until native close."""
    probe = _LoopBoundProbe()
    with SyncCoroutineOwner() as owner:
        for _ in range(6):
            assert run_coro_sync(probe.call(), owner=owner) == "ok"
    assert probe._loop is not None and probe._loop.is_closed()


def test_run_coro_sync_inside_running_loop() -> None:
    """Layer: contract. Direct event-loop use refuses before executing the coroutine."""
    async def _invoke() -> None:
        with pytest.raises(RuntimeError, match="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER"):
            run_coro_sync(asyncio.sleep(0, result="ok"))

    asyncio.run(_invoke())
