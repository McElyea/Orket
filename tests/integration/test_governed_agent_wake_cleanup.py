"""Integration counterexample: a dispatched wake must retain real provider cleanup."""
import asyncio

import httpx
import pytest

from orket.application.services import governed_agent_wake_dispatcher as owner
from tests.helpers.governed_agent_dispatch import configured_dispatcher

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('mode', ['complete', 'cancel', 'timeout'])
@pytest.mark.parametrize('close_failure', [False, True])
async def test_wake_dispatch_retains_provider_close(tmp_path, monkeypatch, mode, close_failure):
    dispatcher, execution, guard, wake, original_id = await configured_dispatcher(tmp_path)
    client = httpx.AsyncClient()
    entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = owner.select_governed_agent_provider

    async def held_close():
        entered.set()
        await release.wait()
        await client.aclose()
        finished.set()
        if close_failure:
            raise OSError('native-close-failed')

    async def select(**kwargs):
        result = await original(**kwargs)
        result._live_provider = client
        return result

    monkeypatch.setattr(client, 'close', held_close, raising=False)
    monkeypatch.setattr(owner, 'select_governed_agent_provider', select)
    deadline = asyncio.timeout(None)

    async def invoke():
        async with deadline:
            return await dispatcher.dispatch(wake=wake, guard=guard)

    task = asyncio.create_task(invoke())
    try:
        await asyncio.wait_for(entered.wait(), 20)
        if mode == 'cancel':
            task.cancel()
        elif mode == 'timeout':
            deadline.reschedule(asyncio.get_running_loop().time() + 0.1)
        await asyncio.sleep(0.15)
        # Existing D responsiveness bound, with a controlled cleanup hold.
        await asyncio.wait_for(asyncio.sleep(0), 0.5)
        assert not task.done() and not finished.is_set()
        if mode == 'cancel':
            task.cancel()
            await asyncio.sleep(0.05)
            assert not task.done()
        release.set()
        expected = OSError if close_failure else (asyncio.CancelledError if mode == 'cancel' else TimeoutError)
        if mode != 'complete' or close_failure:
            with pytest.raises(expected):
                await task
        else:
            result = await task
            assert result.status == 'completed'
        assert client.is_closed and finished.is_set()
        assert await execution.get_run_record(run_id=original_id) is not None
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await client.aclose()
