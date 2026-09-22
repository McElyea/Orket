"""Layer: integration. Actual SDK subprocess model capability over controlled loopback HTTP."""
import asyncio
import builtins
import importlib
import json
import sys
from contextlib import ExitStack
from functools import partial
from pathlib import Path

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.extensions import sdk_workload_subprocess as child
from orket.extensions import workload_artifacts as artifacts
from orket.extensions.sdk_capability_authorization import HostCapabilityControls, build_host_authorization_envelope
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.provider_inference_observation import http_transport
from tests.integration.test_provider_inference_http_inputs import MODEL
from tests.runtime.test_extension_capability_authorization import (
    MODEL_GENERATE_SOURCE,
    _host_controls,
    _install_manager,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_sdk_default_model_capability_runs_in_owned_subprocess(tmp_path, monkeypatch, record_property):
    async def respond(request):
        if request[0].startswith('GET '):
            return 200, {'data': [{'id': MODEL}]}
        record_property('controlled_sdk_request', json.dumps(request))
        return 200, {'model': MODEL, 'choices': [{'index': 0,
            'message': {'role': 'assistant', 'content': 'controlled SDK response'}, 'finish_reason': 'stop'}]}

    async with observed_http_server(respond) as server:
        for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
            monkeypatch.delenv(key, raising=False)
        for key, value in {
            'ORKET_DISABLE_SANDBOX': '1', 'ORKET_LLM_PROVIDER': 'openai_compat',
            'ORKET_LLM_OPENAI_BASE_URL': server[0] + '/v1', 'ORKET_LOCAL_PROMPTING_MODE': 'shadow',
            'ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL': 'false',
            'ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL': 'false',
        }.items():
            monkeypatch.setenv(key, value)
        manager = await _install_manager(tmp_path, module_source=MODEL_GENERATE_SOURCE,
                                         required_capabilities=['model.generate'])
        result = await asyncio.wait_for(manager.run_workload(workload_id='sdk_auth_v1',
            input_config={'model': MODEL, **_host_controls(test_case='default_model_transport',
                expected_result='success', admit_only=['model.generate'])},
            workspace=tmp_path / 'workspace' / 'default', department='core'), 30)
        provenance = json.loads(await asyncio.to_thread(Path(result.provenance_path).read_text, encoding='utf-8'))
        authorization = provenance['sdk_capability_authorization']
        assert result.summary['output'] == {'text': 'controlled SDK response', 'model': MODEL}
        assert authorization['admitted_capabilities'] == authorization['used_capabilities'] == ['model.generate']
        assert authorization['call_records'][0]['capability_id'] == 'model.generate'
        assert [line.split()[0] for line, _ in server[1]] == ['GET', 'POST']
        assert server[1][1][1]['model'] == MODEL
        assert 'hello world' in json.dumps(server[1][1][1]['messages'])


def _native_request(tmp_path, case):
    source = MODEL_GENERATE_SOURCE
    if case in {'work-failure', 'cleanup-work-failure'}:
        source = source.replace("return WorkloadResult(ok=True, output={'text': response.text, 'model': response.model})",
                                "raise ValueError('controlled workload failure')")
    module = 'owned_sdk_' + case.replace('-', '_')
    (tmp_path / (module + '.py')).write_text(source, encoding='utf-8')
    envelope = build_host_authorization_envelope(extension_id='sdk.auth.extension', workload_id='sdk_auth_v1',
        run_id='owned-client-test', declared_capabilities=['model.generate'], controls=HostCapabilityControls())
    return dict(extension=dict(extension_id='sdk.auth.extension', path=str(tmp_path), allowed_stdlib_modules=[]),
        workload=dict(workload_id='sdk_auth_v1', entrypoint=module + ':run_workload'),
        context=dict(workspace_root=str(tmp_path), output_dir=str(tmp_path), input_dir=str(tmp_path),
                     run_id='owned-client-test', seed='invalid' if case == 'partial-context' else 0, config={'model': MODEL}),
        authorization_envelope=envelope.to_payload(), input_payload={},
        child_extra_capabilities=['memory.query'] if case == 'authorization-drift' else [])


def _invoke_native_request(request):
    # A real child exits with its import guards; this in-process observer restores them.
    prior = builtins.__import__, importlib.import_module, list(sys.path), list(sys.meta_path)
    try:
        return child._run_request(request)
    finally:
        builtins.__import__, importlib.import_module = prior[:2]
        sys.path[:], sys.meta_path[:] = prior[2:]


@pytest.mark.parametrize('case', ['success', 'work-failure', 'partial-context', 'authorization-drift',
                                  'cleanup-success-failure', 'cleanup-work-failure'])
async def test_native_sdk_owner_closes_actual_provider_before_result(tmp_path, monkeypatch, case):
    created = []
    real_provider = artifacts.LocalModelCapabilityProvider
    async def respond(request):
        if request[0].startswith('GET '):
            return 200, {'data': [{'id': MODEL}]}
        return 200, {'model': MODEL, 'choices': [{'index': 0,
            'message': {'role': 'assistant', 'content': 'controlled SDK response'}, 'finish_reason': 'stop'}]}

    async with observed_http_server(respond) as server:
        environment = {'ORKET_LLM_PROVIDER': 'openai_compat', 'ORKET_LLM_OPENAI_BASE_URL': server[0] + '/v1',
            'ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL': 'false', 'ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL': 'false'}
        def observe_provider(**options):
            provider = real_provider(**options, environment=environment)
            created.append(provider)
            if case.startswith('cleanup-'):
                close = provider.close
                def failed_close():
                    close()
                    raise OSError('controlled cleanup failure after actual closure')
                provider.close = failed_close
            return provider
        monkeypatch.setattr(artifacts, 'LocalModelCapabilityProvider', observe_provider)
        request = await run_owned_thread(partial(_native_request, tmp_path, case), label='fixture-sdk-request')
        result = await asyncio.wait_for(run_owned_thread(partial(_invoke_native_request, request),
                                       label='fixture-sdk-child-owner'), 10)
        assert len(created) == 1 and created[0]._closed and created[0]._coroutines.closed
        assert http_transport(created[0]._provider).is_closed
        assert result['ok'] is (case == 'success')
        assert len(server[1]) == (0 if case in {'partial-context', 'authorization-drift'} else 2)
        if case == 'authorization-drift':
            assert result['error_code'] == 'E_SDK_CAPABILITY_AUTHORIZATION_DRIFT'
        elif case == 'partial-context':
            assert result['error_code'] == 'ValueError' and 'invalid' in result['error_message']
        elif case == 'work-failure':
            assert result['error_message'] == 'controlled workload failure'
        elif case.startswith('cleanup-'):
            assert result['error_message'] == 'controlled cleanup failure after actual closure'
            assert result['capability_report']['used_capabilities'] == ['model.generate']
            assert result['prior_workload_result']['ok'] is (case == 'cleanup-success-failure')
            if case == 'cleanup-work-failure':
                assert result['prior_workload_result']['error_message'] == 'controlled workload failure'


async def test_sdk_registry_does_not_close_configured_borrowed_model(tmp_path):
    from orket_extension_sdk.llm import GenerateRequest
    async def respond(request):
        if request[0].startswith('GET '):
            return 200, {'data': [{'id': MODEL}]}
        return 200, {'model': MODEL, 'choices': [{'index': 0,
            'message': {'role': 'assistant', 'content': 'borrowed response'}, 'finish_reason': 'stop'}]}

    async with observed_http_server(respond) as server:
        provider = await run_owned_thread(partial(artifacts.LocalModelCapabilityProvider,
            model=MODEL, temperature=0, seed=0, environment={'ORKET_LLM_PROVIDER': 'openai_compat',
                'ORKET_LLM_OPENAI_BASE_URL': server[0] + '/v1', 'ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL': 'false',
                'ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL': 'false'}), label='fixture-borrowed-sdk-provider')
        def build_registry():
            with ExitStack() as resources:
                return artifacts.WorkloadArtifacts.build_sdk_capability_registry(
                    workspace=tmp_path, artifact_root=tmp_path, admitted_capabilities={'model.generate'},
                    input_config={'capabilities': {'model.generate': provider}},
                    own_model_provider=lambda owned: resources.callback(owned.close))
        try:
            registry = await run_owned_thread(build_registry, label='fixture-borrowed-sdk-registry')
            assert registry.llm() is provider and provider.is_available()
            response = await run_owned_thread(partial(provider.generate,
                GenerateRequest(system_prompt='system', user_message='borrowed generation')), label='fixture-borrowed-generation')
            assert response.text == 'borrowed response' and len(server[1]) == 2
        finally:
            await run_owned_thread(provider.close, label='fixture-borrowed-cleanup')
        assert provider._closed and http_transport(provider._provider).is_closed
