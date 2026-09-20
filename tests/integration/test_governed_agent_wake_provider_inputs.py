"""Integration counterexample: a constructed dispatcher retains provider inputs."""
import asyncio
import os

import pytest

from orket.application.services import governed_agent_wake_dispatcher as owner
from tests.helpers.governed_agent_dispatch import configured_dispatcher
from tests.helpers.observed_http_server import observed_http_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('mutation', ['none', 'environment', 'roles'])
@pytest.mark.parametrize('explicit_environment', [False, True])
async def test_wake_keeps_constructed_provider_inputs(tmp_path, monkeypatch, mutation, explicit_environment):
    entered, release = asyncio.Event(), asyncio.Event()

    async def held():
        if not entered.is_set():
            entered.set()
            await release.wait()
        await original()

    async def unavailable(_):
        return 200, {'data': []}

    async with (observed_http_server(unavailable) as (first, first_requests),
                observed_http_server(unavailable) as (second, second_requests)):
        monkeypatch.setenv('ORKET_LLM_OPENAI_BASE_URL', first + '/v1')
        monkeypatch.setenv('ORKET_PROVIDER_QUARANTINE', '')
        for key in ['ORKET_LLM_OPENAI_API_KEY', 'ORKET_MODEL_STREAM_OPENAI_API_KEY']:
            monkeypatch.setenv(key, '')
        roles = {'planner': 'qwen-admitted'}
        configuration = owner.GovernedAgentProviderConfiguration(
            mode='openai_compat', default_model='qwen-admitted', role_models=roles,
            ollama_base_url='', inventory_timeout_seconds=5, capacity_limit=1,
        )
        environment = dict(os.environ) if explicit_environment else None
        dispatcher, execution, guard, wake, original_id = await configured_dispatcher(
            tmp_path, provider=configuration, environment=environment)
        original = guard.ensure_active
        monkeypatch.setattr(guard, 'ensure_active', held)
        task = asyncio.create_task(dispatcher.dispatch(wake=wake, guard=guard))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            if mutation == 'environment':
                monkeypatch.setenv('ORKET_LLM_OPENAI_BASE_URL', second + '/v1')
                if environment is not None:
                    environment['ORKET_LLM_OPENAI_BASE_URL'] = second + '/v1'
            elif mutation == 'roles':
                roles['planner'] = 'qwen-mutated'
            release.set()
            with pytest.raises(ValueError, match='E_AGENT_LOCAL_MODEL_UNAVAILABLE:planner:qwen-admitted:'):
                await asyncio.wait_for(task, 10)
            assert first_requests and not second_requests
            assert await execution.get_run_record(run_id=original_id) is None
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
