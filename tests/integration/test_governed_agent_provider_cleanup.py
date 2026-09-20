"""Integration counterexample: an earlier client failure must not abandon later clients."""
import asyncio

import httpx
import pytest

from orket.application.services.governed_agent_model_provider import GovernedAgentLocalModelProvider

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('fail_first', [False, True])
async def test_governed_provider_attempts_every_owned_client_close(monkeypatch, fail_first):
    first, second = httpx.AsyncClient(), httpx.AsyncClient()

    async def close_first():
        await first.aclose()
        if fail_first:
            raise OSError('first-client-close-failed')

    monkeypatch.setattr(first, 'close', close_first, raising=False)
    monkeypatch.setattr(second, 'close', second.aclose, raising=False)
    provider = GovernedAgentLocalModelProvider({'first': first, 'second': second})
    try:
        if fail_first:
            with pytest.raises(OSError, match='first-client-close-failed'):
                await provider.close()
        else:
            await provider.close()
        assert first.is_closed and second.is_closed
    finally:
        await first.aclose()
        await second.aclose()


@pytest.mark.parametrize('mode', ['cancel', 'timeout'])
@pytest.mark.parametrize('close_failure', [False, True])
async def test_direct_provider_close_drains_clients_after_interruption(monkeypatch, mode, close_failure):
    first, second = httpx.AsyncClient(), httpx.AsyncClient()
    entered, release = asyncio.Event(), asyncio.Event()

    async def close_first():
        entered.set()
        await release.wait()
        await first.aclose()
        if close_failure:
            raise OSError('first-client-close-failed')

    monkeypatch.setattr(first, 'close', close_first, raising=False)
    monkeypatch.setattr(second, 'close', second.aclose, raising=False)
    provider = GovernedAgentLocalModelProvider({'first': first, 'second': second})
    deadline = asyncio.timeout(None)

    async def invoke():
        async with deadline:
            await provider.close()

    task = asyncio.create_task(invoke())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        if mode == 'cancel':
            task.cancel()
        else:
            deadline.reschedule(asyncio.get_running_loop().time() + 0.1)
        await asyncio.sleep(0.15)
        await asyncio.wait_for(asyncio.sleep(0), 0.5)
        assert not task.done() and not first.is_closed
        if mode == 'cancel':
            task.cancel()
            await asyncio.sleep(0.05)
            assert not task.done()
        release.set()
        expected = OSError if close_failure else (asyncio.CancelledError if mode == 'cancel' else TimeoutError)
        with pytest.raises(expected):
            await task
        assert first.is_closed and second.is_closed
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await first.aclose()
        await second.aclose()
