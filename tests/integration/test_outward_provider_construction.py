"""Layer: integration. Default outward composition owns real provider and evidence effects."""
import asyncio
import json
import ssl
import threading

import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services import outward_model_tool_call_service as outward
from orket.core.domain.outward_runs import OutwardRunRecord
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.provider_inference_observation import http_transport
from tests.integration.test_provider_http_environment import _ambient_proxy
from tests.integration.test_provider_inference_http_inputs import MODEL

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('interruption', ['none', 'repeated'])
async def test_outward_default_factory_captures_inputs_and_owns_native_handoff(
    tmp_path, monkeypatch, record_property, interruption):
    entered, release = threading.Event(), threading.Event()
    original = ssl.SSLContext.load_verify_locations
    clients, workers = [], []
    factory = outward.create_configured_model_client

    def held(context, *args, **options):
        workers.append(threading.get_ident())
        entered.set()
        assert release.wait(5), 'outward native construction escaped its owner'
        return original(context, *args, **options)

    def construct(**options):
        client = factory(**options)
        clients.append(client)
        return client

    monkeypatch.setattr(ssl.SSLContext, 'load_verify_locations', held)
    monkeypatch.setattr(outward, 'create_configured_model_client', construct)
    call = {'tool': 'write_file', 'args': {'path': 'proposal-only.txt', 'content': 'declared fixture'}}

    async def response(request):
        if request[0].startswith('GET '):
            return 200, {'data': [{'id': MODEL}]}
        assert request[1]['model'] == MODEL
        return 200, {'choices': [{'message': {'content': json.dumps(call)}, 'finish_reason': 'stop'}],
                     'usage': {'prompt_tokens': 4, 'completion_tokens': 2, 'total_tokens': 6}}

    async with observed_http_server(response) as server:
        _ambient_proxy(monkeypatch, '')
        values = {'ORKET_LLM_PROVIDER': 'openai_compat', 'ORKET_MODEL_STREAM_REAL_MODEL_ID': MODEL,
            'ORKET_LLM_OPENAI_BASE_URL': server[0] + '/v1', 'ORKET_LOCAL_PROMPTING_MODE': 'shadow',
            'ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL': 'false', 'ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL': 'false'}
        for key, value in values.items():
            monkeypatch.setenv(key, value)
        run = OutwardRunRecord(run_id='inference-owner', namespace='issue:inference-owner', status='running',
            current_turn=1, max_turns=1, policy_overrides={}, submitted_at='2026-09-22T00:00:00Z',
            task={'description': 'Propose one file', 'instruction': 'Return one governed tool call.'})
        service = outward.OutwardModelToolCallService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
                                                      workspace_root=tmp_path)
        task = asyncio.create_task(service.produce_governed_tool_call(run=run,
            expected_tool='write_file', governed_tools={'write_file'}))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            assert workers[0] != threading.get_ident()
            await responsive_sqlite(tmp_path / 'responsive.sqlite3', record_property)
            monkeypatch.setenv('ORKET_MODEL_STREAM_REAL_MODEL_ID', 'later-model')
            monkeypatch.setenv('ORKET_LLM_OPENAI_BASE_URL', 'http://127.0.0.1:1/v1')
            if interruption == 'repeated':
                task.cancel()
                await asyncio.sleep(.01)
                task.cancel()
                assert not task.done()
            release.set()
            if interruption == 'repeated':
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(asyncio.shield(task), 5)
                assert not server[1]
            else:
                result = await asyncio.wait_for(asyncio.shield(task), 5)
                assert result.tool_call == call
                evidence = tmp_path / result.model_invocation['model_invocation_ref']
                assert await asyncio.to_thread(evidence.is_file)
                assert [line.split()[0] for line, _ in server[1]] == ['GET', 'POST']
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert len(clients) == 1 and clients[0]._closed and http_transport(clients[0]).is_closed
        assert not await asyncio.to_thread((tmp_path / 'proposal-only.txt').exists)
