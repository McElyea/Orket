"""Integration: native dispatch keeps the admitted request through fence waits."""
import asyncio

import pytest

from tests.helpers.governed_agent_dispatch import configured_dispatcher

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('mutate', [False, True])
async def test_wake_dispatch_keeps_admitted_identity(tmp_path, monkeypatch, mutate):
    dispatcher, execution, guard, wake, original_id = await configured_dispatcher(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    original = guard.ensure_active

    async def held():
        if not entered.is_set():
            entered.set()
            await release.wait()
        await original()

    monkeypatch.setattr(guard, 'ensure_active', held)
    task = asyncio.create_task(dispatcher.dispatch(wake=wake, guard=guard))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        if mutate:
            wake.payload['request']['identity']['run_id'] = 'rotated-wake-run'
        release.set()
        result = await asyncio.wait_for(task, 30)
        assert result.status == 'completed'
        assert await execution.get_run_record(run_id=original_id) is not None
        assert await execution.get_run_record(run_id='rotated-wake-run') is None
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
