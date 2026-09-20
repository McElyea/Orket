"""Integration counterexamples over real TCP with controlled model responses."""
import asyncio
import os

import pytest

from orket.application.services.governed_agent_model_provider import prepare_governed_agent_local_runtime
from orket_extension_sdk import AgentIterationRequest, AgentModelCallRequest
from orket_extension_sdk.agent_fixtures import agent_model_call_request
from tests.helpers.observed_http_server import observed_http_server
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('rotation', ['none', 'environment', 'models', 'quarantine'])
@pytest.mark.parametrize('explicit_environment', [False, True])
async def test_governed_preparation_keeps_admitted_provider_inputs(monkeypatch, rotation, explicit_environment):
    entered, release = asyncio.Event(), asyncio.Event()
    paused = False

    async def primary(request):
        nonlocal paused
        if request[0].startswith('GET '):
            if not paused:
                paused = True
                entered.set()
                await release.wait()
            return 200, {'data': [{'id': 'qwen-fixture'}, {'id': 'qwen-rotated'}]}
        return 200, {'choices': [{'message': {'content': '{"observed":"primary"}'}, 'finish_reason': 'stop'}],
                     'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}

    async def alternate(request):
        if request[0].startswith('GET '):
            return 200, {'data': [{'id': 'qwen-fixture'}, {'id': 'qwen-rotated'}]}
        return 200, {'choices': [{'message': {'content': '{"observed":"rotated"}'}, 'finish_reason': 'stop'}],
                     'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}

    async with observed_http_server(primary) as (first, first_requests), observed_http_server(alternate) as (second, second_requests):
        monkeypatch.setenv('ORKET_LLM_OPENAI_BASE_URL', first + '/v1')
        monkeypatch.setenv('ORKET_PROVIDER_QUARANTINE', '')
        for name in ['ORKET_LLM_OPENAI_API_KEY', 'ORKET_MODEL_STREAM_OPENAI_API_KEY']:
            monkeypatch.setenv(name, '')
        request = AgentIterationRequest.from_wire(agent_request())
        models = {p.role: 'qwen-fixture' for p in request.model_profiles}
        environment = dict(os.environ) if explicit_environment else None
        task = asyncio.create_task(prepare_governed_agent_local_runtime(request=request,
            model_by_role=models, provider='openai_compat', inventory_timeout_seconds=5, environment=environment))
        runtime = None
        try:
            await asyncio.wait_for(entered.wait(), 5)
            if rotation == 'environment':
                monkeypatch.setenv('ORKET_LLM_OPENAI_BASE_URL', second + '/v1')
            elif rotation == 'models':
                models['actor'] = 'qwen-rotated'
            elif rotation == 'quarantine':
                monkeypatch.setenv('ORKET_PROVIDER_QUARANTINE', 'openai_compat')
            if environment is not None:
                environment.update(os.environ)
            release.set()
            runtime = await asyncio.wait_for(task, 10)
            model_request = AgentModelCallRequest.from_wire(agent_model_call_request())
            observation = await runtime.provider.call(request=model_request, profile=runtime.profiles['local.planner'])
            assert observation.response == {'observed': 'primary'}
            assert {t.base_url for t in runtime.targets.values()} == {first + '/v1'}
            assert {t.model_id for t in runtime.targets.values()} == {'qwen-fixture'}
            assert not second_requests
            assert any(first_line.startswith('POST /v1/chat/completions ') for first_line, _ in first_requests)
        finally:
            release.set()
            result, = await asyncio.gather(task, return_exceptions=True)
            if runtime is None and not isinstance(result, BaseException):
                runtime = result
            if runtime is not None:
                await runtime.provider.close()


async def test_captured_quarantine_still_refuses_before_inventory(monkeypatch):
    async def inventory(_):
        return 200, {'data': []}

    async with observed_http_server(inventory) as (url, requests):
        monkeypatch.setenv('ORKET_PROVIDER_QUARANTINE', '')
        request = AgentIterationRequest.from_wire(agent_request())
        with pytest.raises(ValueError, match='quarantined_provider'):
            await prepare_governed_agent_local_runtime(
                request=request, model_by_role={p.role: 'qwen-fixture' for p in request.model_profiles},
                provider='openai_compat', base_url=url + '/v1',
                environment={'ORKET_PROVIDER_QUARANTINE': 'openai_compat'},
            )
        assert not requests
