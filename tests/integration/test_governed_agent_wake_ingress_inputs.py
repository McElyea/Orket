"""Integration counterexample: mutation after validation must not alter queued durable input."""
import asyncio
import json
from copy import deepcopy
from types import MappingProxyType

import pytest

from orket.adapters.storage.async_governed_agent_wake_repository import AsyncGovernedAgentWakeRepository
from orket.application.services.governed_agent_wake_ingress_service import GovernedAgentWakeIngressService
from tests.helpers.governed_agent_cli import write_submission_files
from tests.integration.test_governed_agent_wake_dispatcher import _wake

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('mutation', ['none', 'request', 'continuation', 'decisions'])
@pytest.mark.parametrize('read_only_mapping', [False, True])
async def test_ingress_keeps_validated_payload_through_queue(tmp_path, monkeypatch, mutation, read_only_mapping):
    _, request_path, now = await asyncio.to_thread(write_submission_files, tmp_path)
    request = json.loads(await asyncio.to_thread(request_path.read_text, encoding='utf-8'))
    dispatch = dict(_wake(request, now).payload, continuation_inputs={})
    payload = dict(occurrence_id='capture', target_kind='new_run', workload_id='governed-agent-loop',
                   dispatch=MappingProxyType(dispatch) if read_only_mapping else dispatch)
    admitted = deepcopy(dispatch)
    db = tmp_path / 'agent.sqlite3'
    repository = AsyncGovernedAgentWakeRepository(db)
    service = GovernedAgentWakeIngressService(wake_repository=repository, now_utc=lambda: now.isoformat())
    entered, release = asyncio.Event(), asyncio.Event()
    original = repository._execute

    async def held(operation):
        entered.set()
        await release.wait()
        return await original(operation)

    monkeypatch.setattr(repository, '_execute', held)
    task = asyncio.create_task(service.enqueue(payload, source='api'))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        if mutation == 'request':
            request['identity']['run_id'] = 'changed-after-validation'
        elif mutation == 'continuation':
            dispatch['continuation_inputs']['2'] = []
        elif mutation == 'decisions':
            dispatch['decision_timestamps_utc'][0] = 'not-a-timestamp'
        release.set()
        result = await asyncio.wait_for(task, 10)
        assert result.status == 'enqueued'
        restored = await AsyncGovernedAgentWakeRepository(db).get_wake(wake_id=result.wake.wake_id)
        assert restored.payload == admitted
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
